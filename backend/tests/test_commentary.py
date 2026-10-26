"""Narrator per minute: one checked line per match minute, or a silent minute."""
import asyncio

from app.agents.commentary import check_line, run_commentary
from app.agents.llm import OfflineModel
from app.agents.models import Claim
from app.bus import EventBus
from app.commentary_lane import CommentaryLane, minute_sheet
from app.contracts import SourceEvent, SourceFrame
from app.fixture import MATCH_ID, GeneratorSource
from app.simulator import Simulator
from app.stats import StatsEngine


def drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def sheet_at(clock: str, period: int):
    src = GeneratorSource()
    frames = [i for i in src._items if isinstance(i, SourceFrame)]
    frame = next(f for f in frames if f.clock == clock and f.period == period)
    stats = StatsEngine(src.info.home, src.info.away)
    for i in src._items:
        if i.t > frame.t:
            break
        stats.apply(i)
    events = [i for i in src._items if isinstance(i, SourceEvent) and frame.t - 60 < i.t <= frame.t]
    return minute_sheet(src.info, src.roster, frame, [f for f in frames if frame.t - 60 < f.t <= frame.t],
                        events, stats.agent_snapshot(), None)


def test_minute_sheet_of_the_first_goal():
    sheet = sheet_at("24:00", 1)
    texts = [f.text for f in sheet.facts]
    assert texts[0] == "Goal by Adeyemi-Clarke (9) of Northgate, xG 0.41"
    assert texts[-1] == "Score: Kingsbridge 0-1 Northgate" and sheet.moment.minute == "25"
    # 13 live seconds around the goal say nothing about possession; a normal minute does
    assert not any(t.startswith("Possession in this minute") for t in texts)
    assert any(t.startswith("Possession in this minute: Kingsbridge ") for t in (f.text for f in sheet_at("11:00", 1).facts))


def test_a_line_must_be_short_backed_and_without_new_names():
    sheet = sheet_at("24:00", 1)
    assert check_line("Adeyemi-Clarke scores for Northgate with a 0.41 xG chance.", sheet, []) is None
    assert "words" in check_line(" ".join(["word"] * 26), sheet, [])
    assert "0.55" in check_line("Adeyemi-Clarke scores from a 0.55 xG chance.", sheet, [])
    assert "Halvorsen" in check_line("Adeyemi-Clarke scores after a pass from Halvorsen.", sheet, [])
    claims = [Claim(text="Halvorsen plays in the centre.", fact_ids=["F1"])]
    assert check_line("Adeyemi-Clarke scores, with Halvorsen in the centre.", sheet, claims) is None


class Chatty(OfflineModel):
    name = "chatty"

    def __init__(self, text: str, delay: float = 0):
        self.text, self.delay = text, delay

    async def narrate(self, sheet, claims, prompt):
        await asyncio.sleep(self.delay)
        yield self.text


def test_a_rejected_or_late_line_gives_a_silent_minute():
    sheet = sheet_at("24:00", 1)
    ok = asyncio.run(run_commentary(sheet, [], model=Chatty("Northgate lead through Adeyemi-Clarke."), generation=2))
    assert ok and ok.minute == "25" and ok.generation == 2
    assert asyncio.run(run_commentary(sheet, [], model=Chatty("Northgate lead 3-0 now."))) is None
    assert asyncio.run(run_commentary(sheet, [], model=Chatty("Too late.", delay=1), deadline_s=0.1)) is None


def test_the_simulator_sends_a_line_per_minute_and_drops_it_on_seek():
    async def main():
        bus = EventBus(maxsize=10_000)
        lane = CommentaryLane(OfflineModel())
        sim = Simulator(bus, {MATCH_ID: GeneratorSource}, None, None, lane)
        q = bus.subscribe()
        await sim.load(MATCH_ID, "replay")
        t24 = next(i.t for i in sim._items if isinstance(i, SourceFrame) and i.clock == "24:00")
        sim.seek(t24 - 2)
        drain(q)
        sim.step(0.4)
        await lane.wait()
        first = [d for n, d in drain(q) if n == "commentary"]
        sim.seek(t24 - 2)
        sim.step(0.4)
        sim.seek(0)                        # cancels the line being written
        drain(q)
        await lane.wait()
        return first, [d for n, d in drain(q) if n == "commentary"]

    first, after_seek = asyncio.run(main())
    assert len(first) == 1 and first[0]["minute"] == "25" and first[0]["text"].startswith("Goal by Adeyemi-Clarke (9)")
    assert after_seek == []


def lb_sheet():
    """Minute 3 with today's fact: the left-back inverts 3% of the time (cup match: 34%)."""
    from app.contracts import Fact

    today = Fact(fact_id="T4", text="Kingsbridge's left-back Mbeki (3) moved inside next to the 6 for 3% of the build-up time "
                 "(cup match: 34%, down 31 points)", metric="fb_invert_lb_pct", value=3, team="kba", concept="B3")
    src = GeneratorSource()
    frames = [i for i in src._items if isinstance(i, SourceFrame)]
    frame = next(f for f in frames if f.clock == "03:00")
    stats = StatsEngine(src.info.home, src.info.away)
    return minute_sheet(src.info, src.roster, frame, [f for f in frames if frame.t - 60 < f.t <= frame.t], [],
                        stats.agent_snapshot(), [today])


def test_the_cup_match_is_no_fact_about_today():
    """The line at 3' said "using their inverting left-back" while the left-back inverts 3% today (cup: 34%)."""
    s = lb_sheet()
    reason = check_line("Kingsbridge build patiently using their inverting left-back.", s, [])
    assert reason and "invert" in reason and "cup match" in reason
    assert check_line("Kingsbridge's left-back moves inside 34% of the time.", s, []).startswith(
        "'moves inside' is not what today's facts show")
    assert "34" in check_line("Kingsbridge's left-back is involved 34% of the time.", s, [])
    # an explicit comparison is fine, and so is today's number on its own
    assert check_line("In the cup match Kingsbridge's left-back inverted 34% of the time; today only 3%.", s, []) is None
    assert check_line("Kingsbridge's left-back stays wide, inside only 3% of the build-up time.", s, []) is None


def test_the_commentary_does_not_get_the_scouting_report():
    from app.fixture import SCOUTING_REPORT
    from app.scout_lane import ScoutLane

    prompts = []

    class Recording(OfflineModel):
        name = "recording"

        async def narrate(self, sheet, claims, prompt):
            prompts.append((prompt, claims))
            yield "Kingsbridge have the ball."

    async def main():
        bus = EventBus(maxsize=10_000)
        lane = CommentaryLane(Recording())
        scout = ScoutLane(OfflineModel(), SCOUTING_REPORT)
        sim = Simulator(bus, {MATCH_ID: GeneratorSource}, None, scout, lane)
        await sim.load(MATCH_ID, "replay")
        t3 = next(i.t for i in sim._items if isinstance(i, SourceFrame) and i.clock == "03:00")
        sim.seek(t3 - 2)
        sim.step(0.4)
        await lane.wait()
        return sim

    sim = asyncio.run(main())
    assert sim.state().insights[0].trigger == "scouting"            # the report is on screen ...
    prompt, claims = prompts[-1]
    assert claims == [] and "34%" not in prompt and "Cup match" not in prompt   # ... but not in the commentary's input
    assert "Talk about today's match" in prompt
