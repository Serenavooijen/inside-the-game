"""Scout lane: the tactical analysis during the match, without ever holding up the match.

Triggers (only while the match plays, never while replaying silently after a seek):
- every 5 minutes of match time (5', 10', ... 90'), over the last 5 minutes, compared
  with the 5 minutes before;
- half time, over the whole first half;
- 3 minutes after a substitution (all substitutions of one team at that moment),
  compared with the 10 minutes before it.

At most one Scout runs at a time; triggers that arrive meanwhile wait in a short queue
(the oldest is dropped when it is full). The Tactician runs in a worker thread, the
Scout has its own deadline plus a safety net here. A seek or load cancels everything:
those results belong to an old generation. With TACTICS_ENABLED unset the lane is not
created at all, so nothing changes for the existing moments.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.agents.llm import ModelClient
from app.agents.scout import SCOUT_DEADLINE_S, run_scout
from app.contracts import (
    Fact, Insight, MatchInfo, MatchSnapshot, ScoutingReport, SourceEvent, SourceFrame, TacticalTrigger,
)
from app.sources import MatchItem, PlayerInfo
from app.tactics import Tactician

log = logging.getLogger(__name__)

INTERVAL_MIN = 5
SUB_DELAY_S = 180
QUEUE_MAX = 3
SAFETY_MARGIN_S = 3.0

Publish = Callable[[Insight], None]


def tactics_enabled() -> bool:
    return os.getenv("TACTICS_ENABLED", "").lower() in ("1", "true", "yes", "on")


@dataclass
class Job:
    trigger: TacticalTrigger
    from_t: float
    to_t: float
    prev: tuple[float, float] | None
    subs: list[SourceEvent] = field(default_factory=list)
    events: list[SourceEvent] = field(default_factory=list)
    snapshot: MatchSnapshot | None = None
    generation: int = 0


def load_report(path: Path) -> ScoutingReport | None:
    try:
        return ScoutingReport.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        log.warning("No scouting report at %s; tactical facts without cup baseline", path)
    except Exception:
        log.warning("Scouting report at %s could not be read", path, exc_info=True)
    return None


class ScoutLane:
    def __init__(self, model: ModelClient, report_path: Path | None = None,
                 deadline_s: float = SCOUT_DEADLINE_S) -> None:
        self.model = model
        self.report_path = report_path
        self.deadline_s = deadline_s
        self.report: ScoutingReport | None = None
        self.tactician: Tactician | None = None
        self._queue: list[tuple[Job, Publish]] = []
        self._task: asyncio.Task | None = None
        self._period_start: dict[int, float] = {}
        self._pending_subs: list[tuple[float, list[SourceEvent]]] = []   # (due t, substitutions)

    # ------------------------------------------------------------------ set-up

    async def load(self, info: MatchInfo, roster: dict[str, PlayerInfo], items: list[MatchItem]) -> None:
        """Turn the tracking team-relative once (in a thread, ~0.3 s) and read the cup report."""
        self.cancel_all()
        frames = [i for i in items if isinstance(i, SourceFrame)]
        self.report = await asyncio.to_thread(load_report, self.report_path) if self.report_path else None
        baseline: list[Fact] = list(self.report.facts) if self.report else []
        self.tactician = await asyncio.to_thread(Tactician, info, roster, frames, baseline)
        self._period_start = {}
        for f in frames:
            self._period_start.setdefault(f.period, f.t)

    def cancel_all(self) -> None:
        self._queue.clear()
        self._pending_subs.clear()
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    async def wait(self) -> None:
        """Until the queue is empty and nothing runs (tests)."""
        while self._task and not self._task.done():
            await asyncio.gather(self._task, return_exceptions=True)

    # ------------------------------------------------------------------ triggers

    def on_item(self, item: MatchItem, live: bool, history: list[SourceEvent], snapshot: Callable[[], MatchSnapshot],
                generation: int, publish: Publish) -> None:
        """Called by the simulator for every source item. `live` = the match is playing (not a silent replay)."""
        if self.tactician is None:
            return
        if isinstance(item, SourceEvent):
            if item.type == "substitution":
                same = next((p for p in self._pending_subs if p[1][0].t == item.t and p[1][0].team == item.team), None)
                if same:
                    same[1].append(item)
                else:
                    self._pending_subs.append((item.t + SUB_DELAY_S, [item]))
            elif item.type == "period_end" and item.period == 1 and live:
                start = self._period_start.get(1, 0.0)
                self.submit(Job("half_time", start, item.t - 1, None), history, snapshot, generation, publish)
            return
        # a frame
        due = [p for p in self._pending_subs if p[0] <= item.t]
        for p in due:
            self._pending_subs.remove(p)
            if live:
                subs = p[1]
                self.submit(Job("substitution", subs[0].t, item.t, None, subs=list(subs)), history, snapshot,
                            generation, publish)
        minute = self._interval_minute(item)
        if minute and live:
            start = self._period_start.get(item.period, 0.0)
            frm = max(start, item.t - INTERVAL_MIN * 60 + 1)
            prev = (frm - INTERVAL_MIN * 60, frm - 1) if frm - INTERVAL_MIN * 60 >= start else None
            self.submit(Job("interval", frm, item.t, prev), history, snapshot, generation, publish)

    @staticmethod
    def _interval_minute(f: SourceFrame) -> int | None:
        """5, 10, ... at the frame whose clock reads mm:00 (not the second-half kick-off at 45:00, not added time)."""
        if f.period not in (1, 2) or "+" in f.clock or not f.clock.endswith(":00"):
            return None
        mm = int(f.clock.split(":")[0])
        if mm == 0 or mm % INTERVAL_MIN or (f.period == 2 and mm == 45):
            return None
        return mm

    def submit(self, job: Job, history: list[SourceEvent], snapshot: Callable[[], MatchSnapshot], generation: int,
               publish: Publish) -> None:
        job.events, job.snapshot, job.generation = list(history), snapshot(), generation
        self._queue.append((job, publish))
        if len(self._queue) > QUEUE_MAX:
            self._queue.pop(0)
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._drain())

    # ------------------------------------------------------------------ running

    async def _drain(self) -> None:
        while self._queue:
            job, publish = self._queue.pop(0)
            try:
                await self._run(job, publish)
            except asyncio.CancelledError:
                raise
            except Exception:  # never break the match
                log.warning("Scout job %s at %s failed", job.trigger, job.to_t, exc_info=True)

    async def _run(self, job: Job, publish: Publish) -> None:
        tac = self.tactician
        sheet = await asyncio.to_thread(tac.sheet, job.trigger, job.from_t, job.to_t, job.events, job.snapshot,
                                        job.prev, job.subs or None)
        if sheet is None:
            return
        team = (sheet.facts[0].team or sheet.home).upper()
        heatmap, build_up = await asyncio.to_thread(
            lambda: (tac.heatmap(team, job.from_t, job.to_t), tac.build_up_positions(team, job.from_t, job.to_t)))
        try:
            await asyncio.wait_for(
                run_scout(sheet, publish, generation=job.generation, model=self.model, deadline_s=self.deadline_s,
                          heatmap=heatmap, build_up=build_up),
                timeout=self.deadline_s + SAFETY_MARGIN_S,
            )
        except TimeoutError:
            log.warning("Scout safety net hit at %s", job.to_t)
