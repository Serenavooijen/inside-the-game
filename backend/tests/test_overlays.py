"""Fast lane: the Overlay Composer follows the rules of the mock's recording, live."""
import asyncio
import json
from functools import lru_cache
from pathlib import Path

from app.agents.llm import OfflineModel
from app.bus import EventBus
from app.contracts import SourceFrame
from app.fixture import MATCH_ID, GeneratorSource
from app.overlays import QUIET_AFTER_GOAL_S, OverlayComposer
from app.simulator import Simulator
from app.smart_lane import SmartLane

RECORDING = Path(__file__).resolve().parents[2] / "frontend" / "data" / "matches" / "kba-ngr.json"
FIRST_GOAL_T = 1394


@lru_cache(maxsize=1)
def composed():
    src = GeneratorSource()
    c = OverlayComposer(src.info, src.roster)
    out = []
    for item in src._items:
        out += c.on_frame(item) if isinstance(item, SourceFrame) else c.on_event(item)
    return out


@lru_cache(maxsize=1)
def recorded():
    return json.loads(RECORDING.read_text(encoding="utf-8"))["overlays"]


def keyed(overlays, slot):
    return {(round(o["t"]), o["playerId"]): o for o in overlays if o["slot"] == slot}


def test_shots_and_passes_match_the_recording():
    mine = [o.to_json() for o in composed()]
    for slot in ("shot", "pass"):
        rec, live = keyed(recorded(), slot), keyed(mine, slot)
        assert rec.keys() <= live.keys(), slot
        assert all(live[k]["value"] == rec[k]["value"] and live[k]["to"] == rec[k]["to"] for k in rec), slot
    assert len(keyed(mine, "shot")) == 30


def test_sprints_and_tags_mostly_match_the_recording():
    """The recording also went quiet 15 s before each goal, which needs knowledge of the future."""
    mine = [o.to_json() for o in composed()]
    for slot in ("sprint", "tag"):
        rec, live = keyed(recorded(), slot), keyed(mine, slot)
        assert len(rec.keys() & live.keys()) >= 0.95 * len(rec), slot
    rec, live = keyed(recorded(), "sprint"), keyed(mine, "sprint")
    assert all(live[k]["value"] == rec[k]["value"] for k in rec.keys() & live.keys())


def test_pitch_is_quiet_after_a_goal():
    goals = [i.t for i in GeneratorSource()._items if not isinstance(i, SourceFrame) and i.type == "goal"]
    for g in goals:
        noisy = [o for o in composed() if o.slot in ("pass", "sprint") and g < o.t < g + QUIET_AFTER_GOAL_S]
        assert noisy == [], g


def test_goal_shows_shot_overlay_before_event_and_insight():
    async def main():
        bus = EventBus(maxsize=10_000)
        lane = SmartLane(OfflineModel())
        sim = Simulator(bus, {MATCH_ID: GeneratorSource}, lane)
        q = bus.subscribe()
        await sim.load(MATCH_ID, "live")
        sim.seek(FIRST_GOAL_T - 1)
        while not q.empty():
            q.get_nowait()
        sim.step(0.2)
        await lane.wait()
        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        return sim, msgs

    sim, msgs = asyncio.run(main())
    names = [n for n, _ in msgs]
    shot = next(d for n, d in msgs if n == "overlay" and d["slot"] == "shot")
    assert shot["playerId"] == "NGR-09" and shot["value"] == 0.41 and shot["generation"] == sim.generation
    assert any(n == "overlay" and d["slot"] == "tag" and d["playerId"] == "NGR-09" for n, d in msgs)
    assert names.index("overlay") < names.index("event") < names.index("insight")
