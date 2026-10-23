"""Overlay Composer: the fast lane. Deterministic TV graphics, no LLM.

Same rules as frontend/scripts/import_generator.py (which made the mock's recording),
made incremental so they also work live:
- shot:   every shot, with its xG and where it went;
- tag:    the scorer on a goal or scripted chance, a booked player, and the ball
          carrier about every 30 s;
- pass:   a completed pass of 14 m or more, at most one per 12 s. The quality is a
          PLACEHOLDER from length and progression until there is a pass-difficulty model;
- sprint: a player crossing 23.8 km/h, at most one per 20 s, shown 2 s after the start
          with the peak speed so far.
After a goal the pitch stays quiet for 50 s (the recording also went quiet 15 s
before a goal, which needs knowledge of the future).
"""
from collections import deque

from app.contracts import MatchInfo, Overlay, Point, SourceEvent, SourceFrame
from app.sources import PlayerInfo

PASS_MIN_M = 14.0
PASS_EVERY_S = 12
SPRINT_MS = 23.8 / 3.6
SPRINT_EVERY_S = 20
SPRINT_SHOW_AFTER_S = 2
SPRINT_TRAIL_S = 3
TAG_EVERY_S = 30
QUIET_AFTER_GOAL_S = 50


class OverlayComposer:
    def __init__(self, info: MatchInfo, roster: dict[str, PlayerInfo]) -> None:
        self.info = info
        self.roster = roster
        self.reset()

    def reset(self) -> None:
        self._n = 0
        self._last_pass = self._last_sprint = self._last_tag = -1e9
        self._quiet_until = -1.0
        self._prev_speed: dict[str, float] = {}
        self._trail: deque[SourceFrame] = deque(maxlen=SPRINT_TRAIL_S + 1)
        self._sprint: dict | None = None      # pending: pid, start, from, peak

    # ------------------------------------------------------------------ input

    def on_event(self, e: SourceEvent) -> list[Overlay]:
        if e.type == "goal":
            self._quiet_until = e.t + QUIET_AFTER_GOAL_S
            return []
        if e.type == "shot" and e.player_id and e.end_x is not None:
            out = [self._new(e.t, "shot", e.player_id, value=round(e.details.get("xg") or 0.0, 2),
                             to=Point(x=e.end_x, y=e.end_y))]
            if e.outcome == "goal" or e.details.get("scripted"):
                out.append(self._new(e.t, "tag", e.player_id))
            return out
        if e.type in ("yellow_card", "red_card") and e.player_id:
            return [self._new(e.t, "tag", e.player_id)]
        if e.type == "pass" and self._wants_pass(e):
            self._last_pass = e.t
            return [self._new(e.t, "pass", e.player_id, value=self._pass_quality(e), to=Point(x=e.end_x, y=e.end_y))]
        return []

    def on_frame(self, f: SourceFrame) -> list[Overlay]:
        out = []
        speed = {p.id: p.speed for p in f.players}
        self._trail.append(f)

        if self._sprint:
            s = self._sprint
            s["peak"] = max(s["peak"], speed.get(s["pid"], 0.0))
            if f.t >= s["start"] + SPRINT_SHOW_AFTER_S:
                out.append(self._new(f.t, "sprint", s["pid"], value=round(s["peak"] * 3.6, 1), from_=s["from"]))
                self._sprint = None
        elif f.t - self._last_sprint >= SPRINT_EVERY_S and not self._quiet(f.t):
            starting = [p for p in f.players
                        if p.speed >= SPRINT_MS and self._prev_speed.get(p.id, SPRINT_MS) < SPRINT_MS
                        and not self._is_gk(p.id)]
            if starting:
                p = max(starting, key=lambda p: p.speed)
                start = next((q for q in self._trail[0].players if q.id == p.id), p)
                self._sprint = {"pid": p.id, "start": f.t, "from": Point(x=round(start.x, 1), y=round(start.y, 1)),
                                "peak": p.speed}
                self._last_sprint = f.t

        holder = f.ball.holder_id
        if holder in self.roster and f.t - self._last_tag >= TAG_EVERY_S and not self._quiet(f.t):
            out.append(self._new(f.t, "tag", holder))
            self._last_tag = f.t

        self._prev_speed = speed
        return out

    # ------------------------------------------------------------------ rules

    def _wants_pass(self, e: SourceEvent) -> bool:
        return (e.outcome == "complete" and (e.details.get("length_m") or 0) >= PASS_MIN_M
                and e.end_x is not None and e.t - self._last_pass >= PASS_EVERY_S and not self._quiet(e.t))

    def _pass_quality(self, e: SourceEvent) -> float:
        """PLACEHOLDER: longer and more forward = higher. Replace with a pass-difficulty model."""
        attack = 1 if (e.team == self.info.home) == (e.period in (1, 3)) else -1
        progress = (e.end_x - e.x) * attack
        q = 0.55 + 0.012 * e.details["length_m"] + 0.008 * max(0.0, progress)
        return round(max(0.5, min(0.97, q)), 2)

    def _quiet(self, t: float) -> bool:
        return t < self._quiet_until

    def _is_gk(self, pid: str) -> bool:
        p = self.roster.get(pid)
        return bool(p and p.gk)

    def _new(self, t: float, slot: str, player_id: str, **kw) -> Overlay:
        self._n += 1
        return Overlay(id=f"o-{self._n}", t=t, slot=slot, player_id=player_id, **kw)
