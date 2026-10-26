"""Match Simulator: plays a MatchSource in (scaled) real time and publishes to the EventBus.

Behaves like the frontend's mock (frontend/lib/mock/engine.ts):
- one `tick` per new match second; the frontend interpolates in between;
- `event` for goals, cards and substitutions at the moment they happen;
- `overlay` for the fast lane (shot, pass, sprint, tag) from the Overlay Composer;
- a key event (goal, red card) slows the match to 1x and sets keyMomentId until
  its insight has been on screen for HOLD_AFTER_INSIGHT_S, or KEY_MOMENT_MAX_S has passed;
- every moment the Statistician recognises goes to the smart lane; its insights are
  sent as `insight` (analysing -> streaming -> done), only for the current generation;
- seek raises `generation`, cancels running agents, recomputes everything from
  kick-off and sends `state`.
"""
import asyncio
import time
from bisect import bisect_left, bisect_right
from collections.abc import Callable

from app.bus import EventBus
from app.commentary_lane import CommentaryLane
from app.contracts import (
    Commentary, Insight, MatchEvent, MatchState, Mode, Overlay, SourceEvent, SourceFrame, Speed, Tick,
)
from app.moments import FrameIndex, MatchContext, Statistician
from app.overlays import OverlayComposer
from app.scout_lane import ScoutLane
from app.smart_lane import SmartLane
from app.sources import MatchItem, MatchSource
from app.stats import StatsEngine
from app.wire import markers, minute_from_clock, to_frame, to_match_event

STEP_S = 0.05               # real seconds between simulation steps
KEY_MOMENT_MAX_S = 25.0     # safety net: never stay slowed down longer than this
HOLD_AFTER_INSIGHT_S = 7.0  # keep the finished insight of a key moment on screen this long


class Simulator:
    def __init__(self, bus: EventBus, sources: dict[str, Callable[[], MatchSource]],
                 smart_lane: SmartLane | None = None, scout_lane: ScoutLane | None = None,
                 commentary_lane: CommentaryLane | None = None) -> None:
        self.bus = bus
        self.sources = sources
        self.smart_lane = smart_lane
        self.scout_lane = scout_lane            # tactical analysis, only with TACTICS_ENABLED
        self.commentary_lane = commentary_lane  # a line of commentary per minute, only with TACTICS_ENABLED
        self.source: MatchSource | None = None
        self.mode: Mode = "replay"
        self.t = 0.0
        self.speed: Speed = 10
        self.playing = False
        self.generation = 0
        self.key_moment_id: str | None = None
        self.duration = 0.0
        self.halftime = 0.0
        self.events: list[MatchEvent] = []        # key events up to now
        self.insights: dict[str, Insight] = {}    # latest version per insight id, current generation
        self._items: list[MatchItem] = []
        self._history: list[SourceEvent] = []     # every source event up to now, for the Statistician
        self._frame_at = FrameIndex([])
        self._all_events: list[MatchEvent] = []   # whole match, for replay markers
        self._stats: StatsEngine | None = None
        self._overlays: OverlayComposer | None = None
        self._cursor = 0
        self._frame: SourceFrame | None = None
        self._last_second = 0
        self._speed_before_key: Speed = 10
        self._key_deadline = 0.0
        self._clock = 0.0                         # real seconds since start, drives the key-moment deadline

    @property
    def loaded(self) -> bool:
        return self.source is not None

    # ------------------------------------------------------------------ commands

    async def load(self, match_id: str, mode: Mode) -> None:
        if match_id not in self.sources:
            raise KeyError(match_id)
        source = self.sources[match_id]()
        items = [item async for item in source.items(0)]
        if self.scout_lane:                     # before switching over: the old match keeps running meanwhile
            await self.scout_lane.load(source.info, source.roster, items)
        self._items = items
        self.source, self.mode = source, mode
        self._stats = StatsEngine(source.info.home, source.info.away)
        self._overlays = OverlayComposer(source.info, source.roster)
        self._frame_at = FrameIndex([i for i in self._items if isinstance(i, SourceFrame)])
        self.duration = source.info.duration_s or self._items[-1].t
        self.halftime = next((i.t for i in self._items if isinstance(i, SourceFrame) and i.period == 2), self.duration)
        self._all_events = [e for i in self._items if not isinstance(i, SourceFrame)
                            if (e := to_match_event(i, source.roster))]
        self._reset(0)
        self.playing, self.speed = True, 10
        self._publish_state()

    def play(self) -> None:
        if self.t >= self.duration:
            self._reset(0)
        self.playing = True
        self._publish_tick()

    def pause(self) -> None:
        self.playing = False
        self._publish_tick()

    def set_speed(self, speed: Speed) -> None:
        if self.key_moment_id:
            self._speed_before_key = speed      # applies when the key moment ends
            return
        self.speed = speed
        self._publish_tick()

    def seek(self, t: float) -> None:
        self._reset(round(max(0.0, min(self.duration, t))))
        self._publish_state()

    def end_key_moment(self, moment_id: str) -> None:
        if self.key_moment_id != moment_id:
            return
        self.key_moment_id = None
        self.speed = self._speed_before_key
        self._publish_tick()

    # ------------------------------------------------------------------ time

    async def run(self) -> None:
        """Background task: advance the match in real time."""
        last = time.monotonic()
        while True:
            await asyncio.sleep(STEP_S)
            now = time.monotonic()
            self.step(now - last)
            last = now

    def step(self, dt: float) -> None:
        """Advance `dt` real seconds."""
        self._clock += dt
        if self.key_moment_id and self._clock >= self._key_deadline:
            self.end_key_moment(self.key_moment_id)
        if not self.loaded or not self.playing or self.t >= self.duration:
            return
        self.t = min(self.duration, self.t + dt * self.speed)
        self._advance(self.t)
        second = int(self.t)
        if second != self._last_second:
            self._last_second = second
            self._publish_tick()
        if self.t >= self.duration:
            self.playing = False
            self._publish_tick()

    def _reset(self, t: float) -> None:
        if self.smart_lane:
            self.smart_lane.cancel_all()
        if self.scout_lane:
            self.scout_lane.cancel_all()
        if self.commentary_lane:
            self.commentary_lane.cancel_all()
        if self.key_moment_id:
            self.speed = self._speed_before_key
        self.key_moment_id = None
        self.generation += 1
        self._stats.reset()
        self._overlays.reset()
        self._cursor, self._frame, self.events, self.insights, self._history = 0, None, [], {}, []
        self.t = t
        self._advance(t, publish=False)
        self._last_second = int(t)

    def _advance(self, to: float, publish: bool = True) -> None:
        """Apply every source item with t <= `to`."""
        while self._cursor < len(self._items) and self._items[self._cursor].t <= to:
            item = self._items[self._cursor]
            self._cursor += 1
            self._stats.apply(item)
            if isinstance(item, SourceFrame):
                self._frame = item
                self._publish_overlays(self._overlays.on_frame(item), publish)
                self._scout(item, publish)
                continue
            self._history.append(item)
            self._scout(item, publish)
            overlays = self._overlays.on_event(item)
            event = to_match_event(item, self.source.roster)
            if event:
                self.events.append(event)
            if not publish:
                continue
            if event:
                self.bus.publish("event", event.to_json())
                if event.key:
                    self._start_key_moment(event.id)
            self._publish_overlays(overlays, publish)
            self._detect_moment(item)

    def _scout(self, item: MatchItem, publish: bool) -> None:
        if self.scout_lane:
            self.scout_lane.on_item(item, publish, self._history, self._stats.agent_snapshot, self.generation,
                                    self._on_insight)
        if self.commentary_lane and publish and isinstance(item, SourceFrame):
            tactics = max((i for i in self.insights.values() if i.type == "tactics" and i.phase == "done"),
                          key=lambda i: i.t, default=None)
            self.commentary_lane.on_frame(self.source.info, self.source.roster, item, self._frames_between,
                                          self._history, self._stats.agent_snapshot(), tactics, self.generation,
                                          self._on_commentary)

    def _frames_between(self, a: float, b: float) -> list[SourceFrame]:
        fs, ts = self._frame_at.frames, self._frame_at.ts
        return fs[bisect_left(ts, a):bisect_right(ts, b)]

    def _on_commentary(self, line: Commentary) -> None:
        if line.generation == self.generation:
            self.bus.publish("commentary", line.to_json())

    def _publish_overlays(self, overlays: list[Overlay], publish: bool) -> None:
        if not publish:
            return                                  # replaying silently after a seek: only the state matters
        for o in overlays:
            o.generation = self.generation
            self.bus.publish("overlay", o.to_json())

    def _detect_moment(self, item: SourceEvent) -> None:
        if not self.smart_lane:
            return
        ctx = MatchContext(info=self.source.info, roster=self.source.roster, events=self._history,
                           frame_at=self._frame_at, snapshot=self._stats.agent_snapshot())
        sheet = Statistician(ctx).build(item)
        if sheet:
            self.smart_lane.submit(sheet.moment, sheet, self.generation, self._on_insight)

    def _on_insight(self, insight: Insight) -> None:
        """Called by the smart lane for every update of an insight."""
        if insight.generation != self.generation:
            return                                  # from before a seek: drop it
        self.insights[insight.id] = insight
        self.bus.publish("insight", insight.to_json())
        if insight.phase == "done" and insight.moment_id and insight.moment_id == self.key_moment_id:
            self._key_deadline = min(self._key_deadline, self._clock + HOLD_AFTER_INSIGHT_S)

    def _start_key_moment(self, event_id: str) -> None:
        if self.key_moment_id:
            return
        self.key_moment_id = event_id
        self._speed_before_key, self.speed = self.speed, 1
        self._key_deadline = self._clock + KEY_MOMENT_MAX_S
        self._publish_tick()

    # ------------------------------------------------------------------ views

    def tick(self) -> Tick:
        f = self._frame or self._items[0]
        return Tick(
            t=int(self.t), period=f.period, clock=f.clock, minute=minute_from_clock(f.clock),
            speed=self.speed, playing=self.playing, generation=self.generation,
            frame=to_frame(f, self.source.roster), stats=self._stats.snapshot(),
            key_moment_id=self.key_moment_id, finished=self.t >= self.duration,
        )

    def state(self) -> MatchState:
        return MatchState(
            **self.tick().model_dump(),
            match_id=self.source.info.match_id, mode=self.mode,
            duration=self.duration, halftime=self.halftime,
            events=list(self.events), insights=sorted(self.insights.values(), key=lambda i: i.t),
            markers=markers(self._all_events) if self.mode == "replay" else None,
            scouting=self.scout_lane.report if self.scout_lane else None,
        )

    def _publish_tick(self) -> None:
        self.bus.publish("tick", self.tick().to_json())

    def _publish_state(self) -> None:
        self.bus.publish("state", self.state().to_json())
