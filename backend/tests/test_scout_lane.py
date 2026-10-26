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


def substitution_cards(msgs):
    return [d for n, d in msgs if n == "insight" and d["type"] == "substitution" and d["phase"] == "done"]


def test_what_to_watch_at_the_moment_and_the_impact_8_minutes_later_at_64():
    subs = [i for i in items() if isinstance(i, SourceEvent) and i.type == "substitution" and i.minute == "64"]

    async def scenario(sim, lane, q):
        sim.seek(subs[0].t - 1)
        drain(q)
        sim.step(0.4)                       # the substitutions happen: "what to watch"
        await lane.wait()
        watch = substitution_cards(drain(q))
        sim.seek(subs[0].t + 478)           # replayed silently: the impact stays pending
        drain(q)
        sim.step(0.4)
        await lane.wait()
        return watch, substitution_cards(drain(q))

    watch, impact = run(scenario)
    assert len(watch) == 1 and len(impact) == 1                  # one card per moment, with two changes
    w, i = watch[0]["substitution"], impact[0]["substitution"]
    assert w["stage"] == "watch" and w["kind"] == "shape change" and watch[0]["status"] == "checked"
    assert [p["n"] for p in w["off"]] == [7, 10] and [p["n"] for p in w["on"]] == [18, 20]
    assert watch[0]["text"].startswith("Northgate switch from a 4-4-2 to a 4-3-3 at 64'")
    assert i["stage"] == "impact" and len(i["heatmaps"]) == 2 and impact[0]["observations"]
    assert impact[0]["id"] == f"i-sub-impact-ngr-{round(subs[0].t)}" and impact[0]["status"] in ("checked", "corrected")


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


class RecordingScout(OfflineModel):
    prompts: list[str] = []

    async def scout(self, sheet, prompt):
        RecordingScout.prompts.append(prompt)
        return await super().scout(sheet, prompt)


def test_the_lane_gives_the_scout_its_previous_analysis_and_forgets_it_on_seek():
    RecordingScout.prompts = []

    async def scenario(sim, lane, q):
        sim.seek(t_clock("09:58", 1))
        sim.step(0.4)
        await lane.wait()
        sim.seek(t_clock("14:58", 1))      # a seek forgets the previous analysis ...
        sim.step(0.4)
        await lane.wait()
        sim.step(30.0)                     # ... and the next window (20') gets the one from 15'
        await lane.wait()

    run(scenario, model=RecordingScout())
    first, after_seek, *later = RecordingScout.prompts
    assert "Your previous analysis" not in first and "Your previous analysis" not in after_seek
    assert any("Your previous analysis" in p for p in later)


def test_45_and_90_are_five_minute_moments():
    frame = lambda clock, period: SourceFrame(t=0, period=period, clock=clock, players=[], ball={"x": 0, "y": 0, "live": True})
    assert ScoutLane._interval_minute(frame("45+0:00", 1)) == 45
    assert ScoutLane._interval_minute(frame("90+0:00", 2)) == 90
    assert ScoutLane._interval_minute(frame("45:00", 2)) is None          # second-half kick-off
    assert ScoutLane._interval_minute(frame("45+1:00", 1)) is None
    assert ScoutLane._interval_minute(frame("50:00", 2)) == 50


def test_a_whole_match_has_18_five_minute_cards_and_starts_with_the_scouting_report():
    from app.fixture import SCOUTING_REPORT

    async def scenario(sim, lane, q):
        sim.seek(0)
        while not sim.state().finished:
            sim.step(1.0)                  # 10 match seconds per step at 10x (1 s during key moments)
            await lane.wait()
        await lane.wait()
        return sim.state()

    state = run(scenario, report_path=SCOUTING_REPORT)
    tactics = sorted((i for i in state.insights if i.type == "tactics"), key=lambda i: i.t)
    intervals = [i for i in tactics if i.trigger == "interval"]
    assert len(intervals) == 18
    assert [i.window.label.split("–")[1] for i in intervals] == [f"{m}'" for m in range(5, 95, 5)]
    assert tactics[0].id == "i-tac-scouting" and tactics[0].t == 0 and tactics[0].observations
    assert all(i.phase == "done" and i.status in ("checked", "corrected") for i in intervals)
    # every substitution moment: "what to watch" at the moment, the impact about 8 minutes later
    subs = sorted((i for i in state.insights if i.type == "substitution"), key=lambda i: i.t)
    watch = [i for i in subs if i.substitution.stage == "watch"]
    impact = [i for i in subs if i.substitution.stage == "impact"]
    assert [i.substitution.minute for i in watch] == ["46", "59", "64", "76", "87"]
    assert [i.substitution.minute for i in impact] == ["46", "59", "64", "76", "87"]
    assert all(470 <= b.t - a.t <= 490 for a, b in zip(watch, impact))
    assert all(i.observations and i.status in ("checked", "corrected") for i in impact)


class SilentScout(OfflineModel):
    """A Scout with nothing new to say."""

    async def scout(self, sheet, prompt):
        from app.agents.models import ScoutDraft
        return ScoutDraft(observations=[]), None


def test_no_new_observations_gives_a_status_card_from_the_code():
    async def scenario(sim, lane, q):
        sim.seek(t_clock("09:58", 1))
        drain(q)
        sim.step(0.4)
        await lane.wait()
        return drain(q)

    cards = tactics(run(scenario, model=SilentScout()))
    card = cards[-1]
    assert card["text"] == "No tactical change" and card["status"] == "checked"
    assert card["window"]["label"] == "5'–10'" and card["citedFactIds"]
    assert {o["team"] for o in card["observations"]} == {"kba", "ngr"}
    blocks = " ".join(o["observation"] for o in card["observations"])
    assert "high block" in blocks and "low block" in blocks       # the labels from the facts
    assert all(o["consequence"] == "No tactical change in this window." for o in card["observations"])
