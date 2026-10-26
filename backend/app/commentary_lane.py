"""Commentary lane: one checked line of commentary per match minute, sent as SSE `commentary`.

The Stats Engine part is `minute_sheet`: a small FactSheet with the score, possession in
that minute and the most important action, plus the fact lines behind the latest tactics
card. The Narrator turns it into one sentence (app/agents/commentary.py).

At most one line is being written at a time; a minute that arrives while the previous one
is still busy is skipped. A seek cancels it. Only with TACTICS_ENABLED.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from app.agents.commentary import run_commentary
from app.agents.models import Claim
from app.contracts import (
    Commentary, Fact, FactSheet, Insight, MatchInfo, MatchSnapshot, Moment, SourceEvent, SourceFrame,
)
from app.sources import PlayerInfo
from app.wire import minute_from_clock, team_id

log = logging.getLogger(__name__)

# What a viewer would call the action of the minute, most important first.
PRIORITY = ["goal", "red_card", "shot", "yellow_card", "substitution", "save", "cross", "take_on", "interception"]
LABEL = {"goal": "goal", "red_card": "red card", "shot": "shot", "yellow_card": "yellow card",
         "substitution": "substitution", "save": "save", "cross": "cross", "take_on": "dribble",
         "interception": "interception"}

MIN_POSSESSION_S = 20

Publish = Callable[[Commentary], None]


def minute_sheet(info: MatchInfo, roster: dict[str, PlayerInfo], frame: SourceFrame, minute_frames: list[SourceFrame],
                 minute_events: list[SourceEvent], snapshot: MatchSnapshot, tactics: Insight | None) -> FactSheet:
    """The facts of the minute that ends at `frame`."""
    def who(pid: str | None) -> str:
        p = roster.get(pid or "")
        return f"{p.surname} ({p.n})" if p else (pid or "")

    name = lambda code: info.team_names.get(code or "", code or "")
    home, away = name(info.home), name(info.away)
    minute = minute_from_clock(frame.clock)
    facts: list[tuple[str, str, float | str, list[int]]] = []

    key = sorted((e for e in minute_events if e.type in PRIORITY and e.team),
                 key=lambda e: (PRIORITY.index(e.type), -(e.details.get("xg") or 0)))
    if key:
        e = key[0]
        text = f"{LABEL[e.type].capitalize()} by {who(e.player_id)} of {name(e.team)}"
        if e.type == "substitution":
            text = f"{name(e.team)} substitution: {who(e.details.get('player_in_id'))} on for {who(e.player_id)}"
        elif e.type in ("shot", "goal"):
            # a goal carries no xG itself: it is on the scorer's shot just before it
            shot = e if e.type == "shot" else next(
                (x for x in reversed(minute_events) if x.type == "shot" and x.player_id == e.player_id and x.t <= e.t), None)
            if shot and shot.details.get("xg") is not None:
                text += f", xG {shot.details['xg']:.2f}"
        facts.append((text, "key_action", e.type, [e.event_id]))

    # Possession like the Stats Engine: the team of the last player on the ball, while the ball is live.
    holders, last = [], None
    for f in minute_frames:
        holder = next((p.team for p in f.players if p.id == f.ball.holder_id), None) if f.ball.holder_id else None
        last = holder or last
        if f.ball.live and last:
            holders.append(last)
    if len(holders) >= MIN_POSSESSION_S:        # a minute of stoppages says nothing about possession
        share = round(100 * holders.count(info.home) / len(holders))
        facts.append((f"Possession in this minute: {home} {share}%, {away} {100 - share}%", "minute_possession", share, []))
    s = snapshot
    facts.append((f"Score: {home} {s.score[0]}-{s.score[1]} {away}", "score", f"{s.score[0]}-{s.score[1]}", []))
    if tactics:
        for line in (tactics.evidence or [])[:3]:
            facts.append((line, "tactics_fact", tactics.id, []))

    h, a = team_id(info.home), team_id(info.away)
    return FactSheet(
        moment=Moment(moment_id=f"min-{minute}", t=frame.t, minute=minute, kind="update",
                      headline=f"{home} {s.score[0]}-{s.score[1]} {away}"),
        match_state=snapshot, home=h, away=a, team_names={h: home, a: away},
        facts=[Fact(fact_id=f"F{i}", text=t, metric=m, value=v, source_event_ids=src)
               for i, (t, m, v, src) in enumerate(facts, start=1)],
    )


def tactics_claims(tactics: Insight | None) -> list[Claim]:
    """The latest tactics card's checked observations (and consequences) as claims the line may use."""
    if not tactics or not tactics.observations:
        return []
    out = []
    for o in tactics.observations:
        out.append(Claim(text=o.observation, fact_ids=o.fact_ids))
        out.append(Claim(text=o.consequence, fact_ids=o.fact_ids))
    return out


class CommentaryLane:
    def __init__(self, model, deadline_s: float | None = None) -> None:
        self.model = model
        self.deadline_s = deadline_s
        self._task: asyncio.Task | None = None

    def cancel_all(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    async def wait(self) -> None:
        if self._task:
            await asyncio.gather(self._task, return_exceptions=True)

    @staticmethod
    def is_minute(f: SourceFrame) -> bool:
        if f.period not in (1, 2) or "+" in f.clock or not f.clock.endswith(":00"):
            return False
        mm = int(f.clock.split(":")[0])
        return mm > 0 and not (f.period == 2 and mm == 45)

    def on_frame(self, info: MatchInfo, roster: dict[str, PlayerInfo], frame: SourceFrame,
                 frames: Callable[[float, float], list[SourceFrame]], history: list[SourceEvent],
                 snapshot: MatchSnapshot, tactics: Insight | None, generation: int, publish: Publish) -> None:
        if not self.is_minute(frame) or (self._task and not self._task.done()):
            return                          # not a new minute, or the previous line is still busy: skip
        events = [e for e in history if frame.t - 60 < e.t <= frame.t]
        sheet = minute_sheet(info, roster, frame, frames(frame.t - 59, frame.t), events, snapshot, tactics)
        claims = tactics_claims(tactics)

        async def job():
            try:
                line = await run_commentary(sheet, claims, model=self.model, generation=generation,
                                            source_insight_id=tactics.id if tactics else None,
                                            deadline_s=self.deadline_s)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.warning("Commentary for %s failed", sheet.moment.minute, exc_info=True)
                return
            if line:
                publish(line)

        self._task = asyncio.get_running_loop().create_task(job())
