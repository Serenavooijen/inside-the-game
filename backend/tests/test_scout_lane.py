"""Scout lane: tactical cards every 5 minutes, at half time and after substitutions, without holding up the match."""
import asyncio
import json

from app.agents.llm import OfflineModel
from app.bus import EventBus
from app.contracts import Fact, ScoutingReport, SourceEvent, SourceFrame, TacticalObservation
from app.fixture import MATCH_ID, GeneratorSource
from app.scout_lane import ScoutLane, tactics_enabled
from app.simulator import Simulator


def drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def items():
    return GeneratorSource()._items


def t_clock(clock: str, period: int) -> float:
    return next(i.t for i in items() if isinstance(i, SourceFrame) and i.clock == clock and i.period == period)


class SlowScout(OfflineModel):
    async def scout(self, sheet, prompt):
        await asyncio.sleep(30)


def run(scenario, model=None, report_path=None, **lane_kwargs):
    async def main():
        bus = EventBus(maxsize=10_000)
        lane = ScoutLane(model or OfflineModel(), report_path, **lane_kwargs)
        sim = Simulator(bus, {MATCH_ID: GeneratorSource}, None, lane)
        q = bus.subscribe()
        await sim.load(MATCH_ID, "replay")
        drain(q)
        return await scenario(sim, lane, q)
    return asyncio.run(main())


def tactics(msgs):
    return [d for n, d in msgs if n == "insight" and d["type"] == "tactics" and d["phase"] == "done"]


def test_flag_is_off_by_default(monkeypatch):
    monkeypatch.delenv("TACTICS_ENABLED", raising=False)
    assert not tactics_enabled()
    monkeypatch.setenv("TACTICS_ENABLED", "1")
    assert tactics_enabled()


def test_a_card_every_five_minutes():
    async def scenario(sim, lane, q):
        sim.seek(t_clock("09:58", 1))
        drain(q)
        sim.step(0.4)                       # 4 match seconds at 10x: passes 10:00
        await lane.wait()
        return sim, drain(q)

    sim, msgs = run(scenario)
    cards = tactics(msgs)
    assert len(cards) == 1
    c = cards[0]
    assert c["trigger"] == "interval" and c["window"]["label"] == "5'–10'" and c["minute"] == "11"
    assert c["status"] == "checked" and 1 <= len(c["observations"]) <= 3 and c["generation"] == sim.generation
    assert c["heatmap"]["grid"] and len(c["heatmap"]["grid"]) == 4
    assert c["id"] in {i.id for i in sim.state().insights}


def test_a_card_three_minutes_after_the_substitutions_at_64():
    subs = [i for i in items() if isinstance(i, SourceEvent) and i.type == "substitution" and i.minute == "64"]

    async def scenario(sim, lane, q):
        sim.seek(subs[0].t + 178)           # the substitutions are replayed silently and stay pending
        drain(q)
        sim.step(0.4)
        await lane.wait()
        return drain(q)

    cards = [c for c in tactics(run(scenario)) if c["trigger"] == "substitution"]
    assert len(cards) == 1
    assert "Halvorsen (18) and Diallo-Kerr (20) came on at 64'" in " ".join(cards[0]["evidence"])


def test_a_card_at_half_time_over_the_first_half():
    end = next(i for i in items() if isinstance(i, SourceEvent) and i.type == "period_end" and i.period == 1)

    async def scenario(sim, lane, q):
        sim.seek(end.t - 2)
        drain(q)
        sim.step(0.4)
        await lane.wait()
        return drain(q)

    cards = [c for c in tactics(run(scenario)) if c["trigger"] == "half_time"]
    assert len(cards) == 1 and cards[0]["window"]["label"] == "0'–45+2'"


def test_a_slow_scout_never_holds_up_the_match_and_a_seek_drops_it():
    async def scenario(sim, lane, q):
        sim.seek(t_clock("09:58", 1))
        sim.step(0.4)
        await asyncio.sleep(0.2)            # the Scout is now working
        t_before = sim.t
        sim.step(1.0)                       # the match goes on regardless
        assert sim.t > t_before
        sim.seek(0)
        drain(q)
        await lane.wait()
        return sim, drain(q)

    sim, msgs = run(scenario, model=SlowScout())
    assert tactics(msgs) == []
    assert not [i for i in sim.state().insights if i.type == "tactics"]


def test_the_scout_deadline_gives_a_fallback_card():
    async def scenario(sim, lane, q):
        sim.seek(t_clock("09:58", 1))
        drain(q)
        sim.step(0.4)
        await lane.wait()
        return drain(q)

    cards = tactics(run(scenario, model=SlowScout(), deadline_s=0.2))
    assert len(cards) == 1 and cards[0]["status"] == "fallback" and "timed out" in cards[0]["fallbackReason"]


def test_the_report_is_in_the_state_and_its_facts_are_the_baseline(tmp_path):
    report = ScoutingReport(
        id="kba-ngr-cup", title="Cup round 2", home="kba", away="ngr",
        observations=[TacticalObservation(observation="o", fact_ids=["C1"], consequence="c")],
        facts=[Fact(fact_id="C1", text="Cup match: Kingsbridge's last line without the ball 20 m from their own goal",
                    metric="line_height_m", value=20, team="kba", concept="D1")],
    )
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report.to_json()), encoding="utf-8")

    async def scenario(sim, lane, q):
        sim.seek(t_clock("09:58", 1))
        drain(q)
        sim.step(0.4)
        await lane.wait()
        return sim, drain(q)

    sim, msgs = run(scenario, report_path=path)
    assert sim.state().to_json()["scouting"]["id"] == "kba-ngr-cup"
    card = tactics(msgs)[0]
    assert any("than the cup match (20 m, low block)" in e for e in card["evidence"])


def test_a_missing_report_is_no_problem(tmp_path):
    async def scenario(sim, lane, q):
        return sim

    sim = run(scenario, report_path=tmp_path / "nope.json")
    assert "scouting" not in sim.state().to_json()
