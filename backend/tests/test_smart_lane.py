"""Smart lane: Statistician -> agents -> insight on the stream, and the go/no-go checks around it."""
import asyncio
import json
from pathlib import Path

import pytest

from app.agents.llm import OfflineModel
from app.bus import EventBus
from app.contracts import SourceFrame
from app.fixture import MATCH_ID, GeneratorSource
from app.moments import FrameIndex, MatchContext, Statistician
from app.simulator import HOLD_AFTER_INSIGHT_S, KEY_MOMENT_MAX_S, Simulator
from app.smart_lane import SmartLane
from app.stats import StatsEngine

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "moments"
FIRST_GOAL_T = 1394      # Adeyemi-Clarke 0-1, event 688


def drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def all_fact_sheets():
    """Play the whole match through the Statistician, the way the simulator does."""
    src = GeneratorSource()
    stats = StatsEngine(src.info.home, src.info.away)
    frames = FrameIndex([i for i in src._items if isinstance(i, SourceFrame)])
    history, sheets = [], []
    for item in src._items:
        stats.apply(item)
        if isinstance(item, SourceFrame):
            continue
        history.append(item)
        sheet = Statistician(MatchContext(src.info, src.roster, history, frames, stats.agent_snapshot())).build(item)
        if sheet:
            sheets.append(sheet)
    return sheets


class SlowModel:
    name = "slow"

    async def draft(self, sheet, prompt):
        await asyncio.sleep(30)

    async def narrate(self, sheet, claims, prompt):
        yield ""


def run_scenario(model, scenario, **lane_kwargs):
    async def main():
        bus = EventBus(maxsize=10_000)
        lane = SmartLane(model, **lane_kwargs)
        sim = Simulator(bus, {MATCH_ID: GeneratorSource}, lane)
        q = bus.subscribe()
        await sim.load(MATCH_ID, "live")
        drain(q)
        return await scenario(sim, lane, q)
    return asyncio.run(main())


# ------------------------------------------------------------------ Statistician

def test_moments_of_the_reference_match():
    kinds = [s.moment.kind for s in all_fact_sheets()]
    assert kinds.count("goal") == 4 and kinds.count("red_card") == 1 and kinds.count("yellow_card") == 5
    assert kinds[-1] == "full_time" and "update" in kinds          # half time


def test_every_fact_sheet_follows_the_agent_rules():
    for s in all_fact_sheets():
        assert 3 <= len(s.facts) <= 6, s.moment.moment_id
        assert [f.fact_id for f in s.facts] == [f"F{i}" for i in range(1, len(s.facts) + 1)]
        assert s.home == "kba" and s.team_names == {"kba": "Kingsbridge", "ngr": "Northgate"}


@pytest.mark.parametrize("fixture", sorted(FIXTURES.glob("goal-*.json")), ids=lambda p: p.stem)
def test_goal_facts_match_the_agents_test_moments(fixture):
    """The live Statistician gives the same facts as the hand-checked test moments."""
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    sheet = next(s for s in all_fact_sheets() if s.moment.t == expected["moment"]["t"])
    assert sheet.moment.headline == expected["moment"]["headline"]
    assert [f.text for f in sheet.facts] == [f["text"] for f in expected["facts"]][:6]


# ------------------------------------------------------------------ end to end

def test_goal_end_to_end_overlay_then_checked_insight():
    async def scenario(sim, lane, q):
        sim.seek(FIRST_GOAL_T - 1)
        drain(q)
        sim.step(0.2)                         # the goal happens
        await lane.wait()
        return sim, drain(q)

    sim, msgs = run_scenario(OfflineModel(), scenario)
    names = [n for n, _ in msgs]
    assert names.index("event") < names.index("insight")           # fast lane first
    goal = [d for n, d in msgs if n == "insight" and d["momentId"] == "e-688"]
    assert [d["phase"] for d in goal][0] == "analysing" and goal[-1]["phase"] == "done"
    assert any(d["phase"] == "streaming" for d in goal)
    done = goal[-1]
    assert done["status"] == "checked" and done["type"] == "goal" and done["team"] == "ngr"
    assert done["evidence"] and done["generation"] == sim.generation
    assert sim.state().insights[-1].id == "i-e-688"


def test_key_moment_ends_shortly_after_its_insight():
    async def scenario(sim, lane, q):
        sim.seek(FIRST_GOAL_T - 1)
        sim.step(0.2)
        await lane.wait()
        assert sim.key_moment_id == "e-688"
        sim.step(HOLD_AFTER_INSIGHT_S + 0.1)
        return sim.key_moment_id, sim.speed

    key, speed = run_scenario(OfflineModel(), scenario)
    assert key is None and speed == 10
    assert HOLD_AFTER_INSIGHT_S < KEY_MOMENT_MAX_S


def test_seek_drops_running_agents_and_their_insights():
    async def scenario(sim, lane, q):
        sim.seek(FIRST_GOAL_T - 1)
        sim.step(0.2)
        await asyncio.sleep(0.05)             # the agent is working on the goal
        sim.seek(0)
        drain(q)
        await lane.wait()
        return sim, drain(q)

    sim, msgs = run_scenario(SlowModel(), scenario)
    assert [n for n, _ in msgs if n == "insight"] == []
    assert sim.state().insights == []


def test_safety_net_sends_template_text_when_the_workflow_hangs():
    async def scenario(sim, lane, q):
        sim.seek(FIRST_GOAL_T - 1)
        sim.step(0.2)
        await lane.wait()
        return drain(q)

    msgs = run_scenario(SlowModel(), scenario, safety_net_s=0.2)
    done = [d for n, d in msgs if n == "insight" and d.get("phase") == "done"][-1]
    assert done["status"] == "fallback" and "0.2 s" in done["fallbackReason"]
    assert done["text"].startswith("Goal Northgate: Adeyemi-Clarke (9)")


class StuckModel:
    """A model call stuck in its client: it ignores the deadline and unwinds slowly when cancelled."""
    name = "stuck"

    async def draft(self, sheet, prompt):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            await asyncio.sleep(2)
            raise

    async def narrate(self, sheet, claims, prompt):
        yield ""


def test_a_stuck_model_call_does_not_hold_the_deadline():
    """The workflow's own deadline returns the template text on time, not after the call has unwound."""
    import time

    from app.agents.workflow import run_workflow

    s = all_fact_sheets()[0]

    async def main():
        t0 = time.perf_counter()
        insight = await run_workflow(s.moment, s, None, model=StuckModel(), deadline_s=0.2)
        return insight, time.perf_counter() - t0

    insight, took = asyncio.run(main())
    assert insight.status == "fallback" and "timed out" in insight.fallback_reason
    assert took < 1.0


def test_the_safety_net_holds_against_a_stuck_call():
    async def scenario(sim, lane, q):
        sim.seek(FIRST_GOAL_T - 1)
        sim.step(0.2)
        t0 = asyncio.get_running_loop().time()
        await lane.wait()
        return drain(q), asyncio.get_running_loop().time() - t0

    msgs, took = run_scenario(StuckModel(), scenario, safety_net_s=0.2)
    done = [d for n, d in msgs if n == "insight" and d.get("phase") == "done"]
    assert done and done[-1]["status"] == "fallback"
    assert took < 1.0                      # the published fallback does not wait for the stuck call
