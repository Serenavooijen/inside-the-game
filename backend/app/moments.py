"""Moment Detector and FactSheet builder: the Statistician (code, not an LLM).

For each source event it decides whether it is a moment worth explaining (goal, card,
half time, full time) and builds the FactSheet the agents work from. It only looks at
the past, so it works the same during a live match.

The facts follow the rules in docs/overdracht-agents.md:
- derived numbers go in the text itself ("4 minutes before this goal"): the checker
  only accepts numbers that literally appear in a cited fact;
- the most important fact first, because the fallback text uses it;
- 3-6 facts, each with the event ids it comes from.
"""
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass

from app.contracts import Fact, FactSheet, MatchInfo, MatchSnapshot, Moment, SourceEvent, SourceFrame
from app.sources import PlayerInfo
from app.wire import team_id

MOVE_WINDOW_S = 25          # the move = the scoring team's on-ball actions this long before a goal
MOVE_SHOWN = 4              # actions listed in the move fact
MOVE_LABEL = {"pass": "pass", "cross": "cross", "interception": "interception",
              "ball_recovery": "ball recovery", "take_on": "dribble"}


@dataclass
class MatchContext:
    """What the Statistician may look at: only what has happened so far."""
    info: MatchInfo
    roster: dict[str, PlayerInfo]
    events: list[SourceEvent]                       # every source event up to now, in order
    frame_at: Callable[[float], SourceFrame | None]
    snapshot: MatchSnapshot


def minutes(label: str) -> int:
    """'45+3' -> 48, '68' -> 68."""
    base, _, extra = label.partition("+")
    return int(base) + int(extra or 0)


class Statistician:
    def __init__(self, ctx: MatchContext) -> None:
        self.ctx = ctx
        self.info = ctx.info

    # ------------------------------------------------------------------ helpers

    def who(self, pid: str | None) -> str:
        p = self.ctx.roster.get(pid or "")
        return f"{p.surname} ({p.n})" if p else (pid or "")

    def name(self, team: str | None) -> str:
        return self.info.team_names.get(team or "", team or "")

    def other(self, team: str) -> str:
        return self.info.away if team == self.info.home else self.info.home

    def score_line(self) -> str:
        h, a = self.ctx.snapshot.score
        return f"{self.name(self.info.home)} {h}-{a} {self.name(self.info.away)}"

    def before(self, t: float, type_: str, cond: Callable[[SourceEvent], bool] = lambda e: True) -> list[SourceEvent]:
        return [e for e in self.ctx.events if e.t <= t and e.type == type_ and cond(e)]

    def attacks_right(self, team: str, period: int) -> bool:
        """Home attacks towards x = 105 in the first half (and in the first half of extra time)."""
        return (team == self.info.home) == (period in (1, 3))

    def sheet(self, moment: Moment, facts: list[tuple]) -> FactSheet:
        """facts: (text, metric, value[, unit[, window[, source_event_ids]]])"""
        built = []
        for i, f in enumerate(facts, start=1):
            text, metric, value, unit, window, src = (*f, None, None, None)[:6]
            built.append(Fact(fact_id=f"F{i}", text=text, metric=metric, value=value, unit=unit,
                              window=window, source_event_ids=list(src or [])))
        home, away = team_id(self.info.home), team_id(self.info.away)
        return FactSheet(
            moment=moment, match_state=self.ctx.snapshot, facts=built, home=home, away=away,
            team_names={home: self.name(self.info.home), away: self.name(self.info.away)},
        )

    # ------------------------------------------------------------------ moments

    def build(self, e: SourceEvent) -> FactSheet | None:
        """A FactSheet when `e` is a moment worth explaining, else None."""
        if e.type == "goal":
            return self.goal(e)
        if e.type == "red_card":
            return self.red_card(e)
        if e.type == "yellow_card" and not e.details.get("second_yellow"):
            return self.yellow_card(e)
        if e.type == "period_end" and e.period in (1, 2):
            return self.period_end(e)
        return None

    def goal(self, g: SourceEvent) -> FactSheet:
        team, scorer = g.team, g.player_id
        assist = g.details.get("assist_id")
        headline = (f"Goal {self.name(team)}: {self.who(scorer)}" + (f", assist {self.who(assist)}" if assist else "")
                    + f". {self.score_line()}")
        moment = Moment(moment_id=f"e-{g.event_id}", t=g.t, minute=g.minute, kind="goal",
                        team=team_id(team), player_id=scorer, headline=headline)
        facts = []

        shot = next((e for e in reversed(self.ctx.events) if e.type == "shot" and e.player_id == scorer and e.t <= g.t), None)
        if shot and shot.details.get("xg") is not None:
            xg, xgot = shot.details["xg"], shot.details.get("xgot")
            facts.append((f"Shot xG {xg:.2f}" + (f", xGOT {xgot:.2f}" if xgot is not None else ""),
                          "shot_xg", round(xg, 2), None, None, [shot.event_id]))
            if shot.details.get("distance_m") is not None:
                part = str(shot.details.get("body_part", "foot")).replace("_", " ")
                facts.append((f"Shot from {shot.details['distance_m']:.1f} m with the {part}",
                              "shot_distance", round(shot.details["distance_m"], 1), "m", None, [shot.event_id]))

        move = [e for e in self.ctx.events
                if e.team == team and g.t - MOVE_WINDOW_S <= e.t <= g.t and e.type in MOVE_LABEL]
        if move:
            steps = []
            for e in move:
                label = MOVE_LABEL[e.type]
                if e.type == "pass" and e.details.get("pass_type") not in (None, "pass"):
                    label = e.details["pass_type"].replace("_", " ")
                steps.append((f"{self.who(e.player_id)} {label}", e.player_id, e.event_id))
            shown = steps[-MOVE_SHOWN:]
            n_players = len({pid for _, pid, _ in shown})
            facts.append((f"The move ({n_players} players, {len(shown)} actions): " + " → ".join(s for s, _, _ in shown),
                          "move", len(steps), None, None, [eid for _, _, eid in shown]))
            last_pass = next((e for e in reversed(move) if e.type in ("pass", "cross")), None)
            depth = self.deepest_defender_m(self.other(team), last_pass) if last_pass else None
            if depth is not None:
                facts.append((f"{self.name(self.other(team))}'s deepest defender was {depth} m from goal when the last pass was played",
                              "defensive_line", depth, "m", None, [last_pass.event_id]))

        for pid, role in ((scorer, "scorer"), (assist, "assist")):
            sub = next((e for e in self.before(g.t, "substitution") if e.details.get("player_in_id") == pid), None) if pid else None
            if sub:
                facts.append((f"{self.who(pid)} came on at {sub.minute}', {minutes(g.minute) - minutes(sub.minute)} minutes before this goal",
                              f"{role}_sub_minute", sub.minute, None, None, [sub.event_id]))

        xg_h, xg_a = self.ctx.snapshot.xg
        facts.append((f"xG so far: {self.name(self.info.home)} {xg_h:.2f}, {self.name(self.info.away)} {xg_a:.2f}",
                      "xg_cum", xg_h if team == self.info.home else xg_a))
        return self.sheet(moment, facts[:6])

    def yellow_card(self, c: SourceEvent) -> FactSheet:
        pid, team = c.player_id, c.team
        moment = Moment(moment_id=f"e-{c.event_id}", t=c.t, minute=c.minute, kind="yellow_card",
                        team=team_id(team), player_id=pid, headline=f"Yellow card for {self.who(pid)}, {self.name(team)}")
        fouls = self.before(c.t, "foul", lambda e: e.player_id == pid)
        yellows = self.before(c.t, "yellow_card", lambda e: e.team == team and not e.details.get("second_yellow"))
        facts = []
        if c.details.get("reason"):
            facts.append((f"Referee's reason: {c.details['reason']}", "card_reason", "reason", None, None, [c.event_id]))
        facts.append((f"{self.who(pid)} committed {len(fouls)} foul(s) before the booking", "fouls", len(fouls),
                      None, None, [e.event_id for e in fouls]))
        facts.append((f"{self.name(team)} now have {len(yellows)} yellow card(s)", "team_yellow_cards", len(yellows),
                      None, None, [e.event_id for e in yellows]))
        return self.sheet(moment, facts)

    def red_card(self, r: SourceEvent) -> FactSheet:
        pid, team = r.player_id, r.team
        first = next((e for e in self.before(r.t, "yellow_card", lambda e: e.player_id == pid)
                      if not e.details.get("second_yellow")), None)
        second = first is not None
        moment = Moment(moment_id=f"e-{r.event_id}", t=r.t, minute=r.minute, kind="red_card", team=team_id(team),
                        player_id=pid,
                        headline=f"Red card{' (second yellow)' if second else ''} for {self.who(pid)}, {self.name(team)}")
        on_pitch = self.ctx.snapshot.players_on_pitch[0 if team == self.info.home else 1]
        facts = [(f"{self.name(team)} are down to {on_pitch} players", "players_on_pitch", on_pitch, None, None, [r.event_id])]
        if first:
            facts.append((f"{self.who(pid)} was booked earlier, at {first.minute}'", "first_yellow_minute", first.minute,
                          None, None, [first.event_id]))
        fouls = self.before(r.t, "foul", lambda e: e.player_id == pid)
        facts.append((f"{self.who(pid)} committed {len(fouls)} fouls before the red card", "fouls", len(fouls),
                      None, None, [e.event_id for e in fouls]))
        passes = self.before(r.t, "pass", lambda e: e.player_id == pid)
        team_passes = self.before(r.t, "pass", lambda e: e.team == team)
        if team_passes:
            share = round(100 * len(passes) / len(team_passes))
            facts.append((f"{self.who(pid)} made {len(passes)} of {self.name(team)}'s {len(team_passes)} passes so far ({share}%)",
                          "pass_share", share, "%"))
        return self.sheet(moment, facts)

    def period_end(self, e: SourceEvent) -> FactSheet:
        half = e.period == 1
        moment = Moment(moment_id="half-time" if half else "full-time", t=e.t, minute=e.minute,
                        kind="update" if half else "full_time",
                        headline=f"{'Half time' if half else 'Full time'}: {self.score_line()}")
        s, h, a = self.ctx.snapshot, self.name(self.info.home), self.name(self.info.away)
        big = self.before(e.t, "shot", lambda x: bool(x.details.get("big_chance")))
        big_h = sum(1 for x in big if x.team == self.info.home)
        facts = [
            (f"xG: {h} {s.xg[0]:.2f}, {a} {s.xg[1]:.2f}", "xg", s.xg[0]),
            (f"Shots: {h} {s.shots[0]}, {a} {s.shots[1]}", "shots", s.shots[0]),
            (f"Possession: {h} {round(s.possession[0])}%, {a} {round(s.possession[1])}%", "possession", round(s.possession[0]), "%"),
            (f"Big chances: {h} {big_h}, {a} {len(big) - big_h}", "big_chances", len(big), None, None, [x.event_id for x in big]),
        ]
        return self.sheet(moment, facts)

    # ------------------------------------------------------------------ tracking

    def deepest_defender_m(self, team: str, at: SourceEvent) -> int | None:
        """Distance from their own goal of the deepest outfield player of `team` at event `at`."""
        frame = self.ctx.frame_at(at.t)
        if frame is None:
            return None
        own_goal_x = 0.0 if self.attacks_right(team, at.period) else 105.0
        d = [abs(p.x - own_goal_x) for p in frame.players
             if p.team == team and not (self.ctx.roster.get(p.id) and self.ctx.roster[p.id].gk)]
        return round(min(d)) if d else None


class FrameIndex:
    """frame_at(t): the latest frame at or before t."""

    def __init__(self, frames: list[SourceFrame]) -> None:
        self.frames = frames
        self.ts = [f.t for f in frames]

    def __call__(self, t: float) -> SourceFrame | None:
        i = bisect_right(self.ts, t)
        return self.frames[i - 1] if i else None
