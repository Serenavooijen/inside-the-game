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

from app.agents.deadline import within
from app.agents.llm import ModelClient
from app.agents.perspectives import perspectives_enabled, run_perspectives
from app.agents.scout import SCOUT_DEADLINE_S, run_scout, scouting_card, status_card, watch_card
from app.contracts import (
    Fact, Insight, MatchInfo, MatchSnapshot, ScoutingReport, SourceEvent, SourceFrame, TacticalObservation,
    TacticalTrigger,
)
from app.sources import MatchItem, PlayerInfo
from app.tactics import Tactician

log = logging.getLogger(__name__)

INTERVAL_MIN = 5
SUB_WATCH_S = 2             # "what to watch": as soon as the new roles are in the tracking
SUB_IMPACT_S = 480          # "impact": about 8 minutes after the substitution
QUEUE_MAX = 6               # a 5-minute card must never be dropped
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
    stage: str | None = None    # substitutions: "watch" or "impact"
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
        self._pending_subs: list[tuple[float, str, list[SourceEvent]]] = []   # (due t, stage, substitutions)
        self._previous: list[TacticalObservation] = []   # the last checked analysis, so advice is not repeated
        self.last_facts: list[Fact] = []                  # today's facts of the last live sheet (for the commentary)
        self.perspectives = perspectives_enabled()       # PERSPECTIVES_ENABLED: per club "How to beat {opponent}"
        self._side: set[asyncio.Task] = set()             # running club variants (cancelled on seek, like the queue)

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
        self._previous = []
        self.last_facts = []
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        for t in list(self._side):
            t.cancel()

    async def wait(self) -> None:
        """Until the queue is empty and nothing runs (tests)."""
        while (self._task and not self._task.done()) or self._side:
            await asyncio.gather(*([self._task] if self._task else []), *self._side, return_exceptions=True)

    # ------------------------------------------------------------------ triggers

    def on_item(self, item: MatchItem, live: bool, history: list[SourceEvent], snapshot: Callable[[], MatchSnapshot],
                generation: int, publish: Publish) -> None:
        """Called by the simulator for every source item. `live` = the match is playing (not a silent replay)."""
        if self.tactician is None:
            return
        if isinstance(item, SourceEvent):
            if item.type == "substitution":
                same = [p for p in self._pending_subs if p[2][0].t == item.t and p[2][0].team == item.team]
                if same:                        # one card per substitution moment, also with several changes
                    same[0][2].append(item)     # the watch and impact entries share this list
                else:
                    group = [item]
                    self._pending_subs.append((item.t + SUB_WATCH_S, "watch", group))
                    self._pending_subs.append((item.t + SUB_IMPACT_S, "impact", group))
            elif item.type == "period_end" and item.period == 1 and live:
                start = self._period_start.get(1, 0.0)
                self.submit(Job("half_time", start, item.t - 1, None), history, snapshot, generation, publish)
            return
        # a frame
        due = [p for p in self._pending_subs if p[0] <= item.t]
        for p in due:
            self._pending_subs.remove(p)
            if live:
                _, stage, subs = p
                self.submit(Job("substitution", subs[0].t, item.t, None, subs=list(subs), stage=stage), history,
                            snapshot, generation, publish)
        minute = self._interval_minute(item)
        if minute and live:
            start = self._period_start.get(item.period, 0.0)
            frm = max(start, item.t - INTERVAL_MIN * 60 + 1)
            prev = (frm - INTERVAL_MIN * 60, frm - 1) if frm - INTERVAL_MIN * 60 >= start else None
            self.submit(Job("interval", frm, item.t, prev), history, snapshot, generation, publish)

    @staticmethod
    def _interval_minute(f: SourceFrame) -> int | None:
        """5, 10, ... 90 at the frame whose clock reads mm:00. 45' and 90' are "45+0:00" and "90+0:00" (the clock
        runs on into added time); not the second-half kick-off at 45:00."""
        if f.period not in (1, 2) or not f.clock.endswith(":00"):
            return None
        mm_text = f.clock.split(":")[0]
        if "+" in mm_text:
            base, extra = mm_text.split("+")
            return int(base) if extra == "0" and int(base) == 45 * f.period else None
        mm = int(mm_text)
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
        if job.stage == "watch":                # code only, no model
            sheet = await asyncio.to_thread(tac.substitution_sheet, job.subs, job.events, job.to_t, "watch", job.snapshot)
            publish(watch_card(sheet, job.generation))
            return
        if job.stage == "impact":
            sheet = await asyncio.to_thread(tac.substitution_sheet, job.subs, job.events, job.to_t, "impact", job.snapshot)
        else:
            sheet = await asyncio.to_thread(tac.sheet, job.trigger, job.from_t, job.to_t, job.events, job.snapshot,
                                            job.prev, job.subs or None)
        if sheet is not None and job.stage is None:
            self.last_facts = list(sheet.facts)     # today only: the cup baseline is a separate list
        if sheet is None or all(f.metric == "game_state" for f in sheet.facts):
            await self._status(job, publish, sheet=sheet)    # too few facts: still a card, made by the code
            return
        team = (sheet.facts[0].team or sheet.home).upper()
        heatmap, build_up = (None, None) if job.stage else await asyncio.to_thread(   # a substitution card has its own
            lambda: (tac.heatmap(team, job.from_t, job.to_t), tac.build_up_positions(team, job.from_t, job.to_t)))
        try:
            insight = await within(
                run_scout(sheet, publish, generation=job.generation, model=self.model, deadline_s=self.deadline_s,
                          heatmap=heatmap, build_up=build_up, previous=self._previous),
                self.deadline_s + SAFETY_MARGIN_S,
            )
            if insight.status != "fallback" and insight.observations:
                self._previous = list(insight.observations)
                if self.perspectives and job.stage is None:     # tactics cards, not substitution cards
                    self._spawn(self._perspectives(sheet, insight, publish))
            if not insight.observations:        # nothing new from the Scout: the status card replaces it
                await self._status(job, publish, insight.rejected_claims, sheet)
        except TimeoutError:
            log.warning("Scout safety net hit at %s", job.to_t)

    def _spawn(self, coro) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._side.add(task)
        task.add_done_callback(self._side.discard)

    async def _perspectives(self, sheet, insight: Insight, publish: Publish) -> None:
        """Both clubs' variants in parallel, after the neutral card; then the same card again with `perspectives`.
        The queue goes on meanwhile; the semaphore keeps it at 3 Scout calls at once."""
        try:
            found, tokens, latency = await run_perspectives(sheet, model=self.model)
        except asyncio.CancelledError:
            raise
        except Exception:  # never break the match: the neutral card stays
            log.warning("Perspectives for %s failed", insight.id, exc_info=True)
            return
        log.info("Perspectives %s: %s · %d tokens · %d ms", insight.id,
                 ", ".join(f"{t} {p.status}{' (' + p.reason + ')' if p.reason else ''}" for t, p in found.items()),
                 tokens, latency)
        publish(insight.model_copy(update={"perspectives": found}))

    async def _status(self, job: Job, publish: Publish, rejected: list | None = None, sheet=None) -> None:
        tac = self.tactician
        if job.stage == "impact" and sheet is not None:     # a substitution keeps its own card, from its own facts
            publish(status_card(sheet, job.generation, rejected=rejected))
            return
        sheet = await asyncio.to_thread(tac.status_sheet, job.trigger, job.from_t, job.to_t, job.events, job.snapshot)
        team = sheet.home.upper()
        heatmap = await asyncio.to_thread(tac.heatmap, team, job.from_t, job.to_t)
        publish(status_card(sheet, job.generation, heatmap, rejected=rejected))

    def kickoff_card(self, generation: int) -> Insight | None:
        """The scouting report as the first card of the match, or None without a report."""
        return scouting_card(self.report, generation) if self.report else None
