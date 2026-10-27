"""Translator: checked English -> nl/es/fr, the translation check, the cache, the deadline and the stream."""
import asyncio

from app.agents.checker import check_translation
from app.agents.llm import OfflineModel
from app.agents.models import TranslationDraft
from app.agents.translator import TranslationCache, languages, segments, translate
from app.bus import EventBus
from app.contracts import Commentary, Insight, TacticalObservation
from app.fixture import MATCH_ID, GeneratorSource
from app.simulator import Simulator
from app.smart_lane import SmartLane
from app.translation_lane import TranslationLane

NAMES = {"Kingsbridge", "Northgate", "Adeyemi-Clarke", "Duarte", "Okafor"}
SOURCE = "Adeyemi-Clarke scores for Northgate with a shot of 0.41 xG, 4 minutes after Duarte's chance."
DUTCH = "Adeyemi-Clarke scoort voor Northgate met een schot van 0,41 xG, 4 minuten na de kans van Duarte."
FIRST_GOAL_T = 1394


def goal(text=SOURCE, **kw) -> Insight:
    return Insight(id="i-e-688", t=FIRST_GOAL_T, minute="24", type="goal", text=text, **{"status": "checked", **kw})


class Phrasebook:
    """A Translator that returns what the test asks, and counts its calls."""

    name = "phrasebook"

    def __init__(self, out: dict[str, str] | None = None, delay_s: float = 0.0):
        self.out, self.delay_s, self.calls = out or {}, delay_s, []

    async def translate(self, lang, texts, prompt):
        self.calls.append((lang, list(texts)))
        await asyncio.sleep(self.delay_s)
        return TranslationDraft(texts=[self.out.get(t, f"[{lang}] {t}") for t in texts]), 120


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------ the check

def test_a_translation_with_another_number_is_rejected():
    wrong = DUTCH.replace("0,41", "0,52")       # injected on purpose: the Translator "misreads" the xG
    reason = check_translation(SOURCE, wrong, NAMES)
    assert reason and "0.52" in reason and "0.41" in reason
    assert check_translation(SOURCE, DUTCH.replace("4 minuten", "5 minuten"), NAMES)


def test_a_translation_with_a_new_name_is_rejected():
    reason = check_translation(SOURCE, DUTCH.replace("de kans van Duarte", "de kans van Duarte en Rasmussen"), NAMES)
    assert reason == "Name(s) not in the English source: Rasmussen"
    # a name that goes missing is rejected too
    assert "Duarte" in check_translation(SOURCE, DUTCH.replace("van Duarte", "van hem"), NAMES)


def test_decimal_comma_and_point_are_the_same_number():
    assert check_translation(SOURCE, DUTCH, NAMES) is None
    assert check_translation("xG 1.52 in 45+2 minutes", "xG 1,52 en 45+2 minutos", NAMES) is None
    # English number words count as digits: "two" in the source is the 2 of the translation
    assert check_translation("Northgate had two shots.", "Northgate tuvo 2 tiros.", NAMES) is None


def test_a_translation_that_is_far_too_long_is_rejected():
    assert check_translation("Kingsbridge press high.", "Kingsbridge " + "zet heel erg hoog druk " * 6 + ".", NAMES)
    assert check_translation(SOURCE, "", NAMES) == "Empty translation"


# ------------------------------------------------------------------ the workflow

def test_checked_translation_per_language_and_rejected_keeps_english():
    model = Phrasebook({SOURCE: DUTCH})
    out = run(translate(goal(), NAMES, model=model, cache=TranslationCache(), langs=["nl"]))
    assert out["nl"].status == "checked" and out["nl"].text == DUTCH and out["nl"].tokens == 120

    bad = Phrasebook({SOURCE: DUTCH.replace("0,41", "0,52")})
    out = run(translate(goal(), NAMES, model=bad, cache=TranslationCache(), langs=["nl"]))
    assert out["nl"].status == "rejected" and out["nl"].text is None and "0.52" in out["nl"].reason


def test_a_timeout_falls_back_to_english():
    slow = Phrasebook(delay_s=5)
    out = run(translate(goal(), NAMES, model=slow, cache=TranslationCache(), langs=["nl", "fr"], deadline_s=0.2))
    for lang in ("nl", "fr"):
        assert out[lang].status == "rejected" and out[lang].text is None
        assert out[lang].reason == "Translation timed out after 0.2 s"


def test_the_cache_translates_a_text_only_once():
    model, cache = Phrasebook({SOURCE: DUTCH}), TranslationCache()
    run(translate(goal(), NAMES, model=model, cache=cache, langs=["nl", "es"]))
    assert len(model.calls) == 2 and len(cache) == 2
    # the same text again, as after a seek (a new generation): straight from the cache, no model call
    again = run(translate(goal(generation=3), NAMES, model=model, cache=cache, langs=["nl", "es"]))
    assert len(model.calls) == 2 and again["nl"].text == DUTCH and again["nl"].status == "checked"


def test_tactics_cards_translate_observation_consequence_and_coach_action_not_the_evidence():
    o = TacticalObservation(observation="Northgate's line sits at 31 m.", fact_ids=["T1"],
                            consequence="Kingsbridge find space behind.", coach_action="Step up.")
    card = Insight(id="i-tac-interval-600", t=600, minute="10", type="tactics", text=o.observation, status="checked",
                   observations=[o], evidence=["Northgate line height 31 m"])
    assert segments(card) == [o.observation, o.consequence, o.coach_action]
    out = run(translate(card, NAMES, model=OfflineModel(), cache=TranslationCache(), langs=["es"]))
    obs = out["es"].observations[0]
    assert (obs.observation, obs.consequence, obs.coach_action) == (
        "[es] Northgate's line sits at 31 m.", "[es] Kingsbridge find space behind.", "[es] Step up.")
    assert card.evidence == ["Northgate line height 31 m"]


def test_only_checked_english_is_translated(monkeypatch):
    lane = TranslationLane(OfflineModel(), langs=["nl"])
    assert lane.cached(goal(status="fallback")) is None
    calls = []
    lane.submit(goal(status="fallback"), calls.append)
    lane.submit(goal(phase="streaming"), calls.append)
    assert not lane._tasks
    monkeypatch.setenv("ITG_LANGUAGES", "nl, es,fr,en,ar")
    assert languages() == ["nl", "es", "fr"]          # English is the source; no right-to-left languages yet
    monkeypatch.setenv("ITG_LANGUAGES", "")
    assert languages() == []


# ------------------------------------------------------------------ on the stream

def drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def run_match(model, scenario, translator=None):
    async def main():
        bus = EventBus(maxsize=10_000)
        lane, tl = SmartLane(OfflineModel()), TranslationLane(translator or model, langs=["nl", "es", "fr"])
        sim = Simulator(bus, {MATCH_ID: GeneratorSource}, lane, translation_lane=tl)
        q = bus.subscribe()
        await sim.load(MATCH_ID, "live")
        drain(q)
        return await scenario(sim, lane, tl, q)
    return asyncio.run(main())


def test_the_goal_goes_out_in_english_first_then_once_more_with_checked_translations():
    async def scenario(sim, lane, tl, q):
        sim.seek(FIRST_GOAL_T - 1)
        drain(q)
        sim.step(0.2)
        await lane.wait()
        await tl.wait()
        return sim, drain(q)

    sim, msgs = run_match(OfflineModel(), scenario)
    goal_msgs = [d for n, d in msgs if n == "insight" and d["id"] == "i-e-688"]
    english = [d for d in goal_msgs if "translations" not in d]
    assert english[-1]["phase"] == "done" and english[-1]["status"] == "checked"
    last = goal_msgs[-1]
    assert last["text"] == english[-1]["text"]                 # the English text is unchanged
    assert set(last["translations"]) == {"nl", "es", "fr"}
    assert all(t["status"] == "checked" and t["text"].startswith(f"[{lang}] ") for lang, t in last["translations"].items())
    assert sim.insights["i-e-688"].translations["nl"].status == "checked"


def test_translations_of_an_old_generation_are_dropped():
    async def scenario(sim, lane, tl, q):
        sim.seek(FIRST_GOAL_T - 1)
        sim.step(0.2)
        await lane.wait()                      # the English card is done, the translation is running
        sim.seek(0)
        drain(q)
        await tl.wait()
        return sim, drain(q)

    sim, msgs = run_match(None, scenario, translator=Phrasebook(delay_s=0.3))
    assert [d for n, d in msgs if n == "insight" and d.get("translations")] == []
    assert "i-e-688" not in sim.insights


def test_commentary_line_is_sent_again_with_its_translations():
    async def scenario(sim, lane, tl, q):
        line = Commentary(t=600, minute="10", text="Kingsbridge keep the ball in midfield.", generation=sim.generation)
        sim._on_commentary(line)
        await tl.wait()
        return drain(q)

    msgs = [d for n, d in run_match(OfflineModel(), scenario) if n == "commentary"]
    assert "translations" not in msgs[0] and msgs[1]["translations"]["fr"]["text"].startswith("[fr] Kingsbridge")


# ------------------------------------------------------------------ model set-ups

def test_agent_framework_translator_with_structured_output():
    from app.agents.llm import AgentFrameworkModel
    from tests.agents import fake_openai

    url, srv = fake_openai.start()
    try:
        fake_openai.STATE.update(wrong=False, slow_s=0)
        model = AgentFrameworkModel(name="fake", base_url=url, api_key="test", analyst_model="a", narrator_model="n")
        out = run(translate(goal(), NAMES, model=model, cache=TranslationCache(), langs=["fr"]))
        assert out["fr"].status == "checked" and out["fr"].text == f"[fr] {SOURCE}" and out["fr"].tokens == 160
        call = fake_openai.STATE["requests"][-1]
        assert call["model"] == "a" and "texts" in str(call["response_format"])   # MODEL_TRANSLATOR defaults to the Analyst's
    finally:
        srv.shutdown()


def test_hosted_translator_is_built_only_with_a_version(monkeypatch):
    from agent_framework.foundry import FoundryAgent

    from app.agents.llm import model_from_env

    for k, v in {"FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/itg",
                 "FOUNDRY_ANALYST_AGENT_VERSION": "1", "FOUNDRY_NARRATOR_AGENT_VERSION": "1",
                 "AZURE_CREDENTIAL": "default"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("FOUNDRY_TRANSLATOR_AGENT_VERSION", raising=False)
    model = model_from_env("foundry-agents")
    assert model.translator is None
    out = run(translate(goal(), NAMES, model=model, cache=TranslationCache(), langs=["nl"]))
    assert out["nl"].status == "rejected" and out["nl"].reason == "Translator error: NoTranslatorAgent"
    monkeypatch.setenv("FOUNDRY_TRANSLATOR_AGENT_VERSION", "1")
    assert isinstance(model_from_env("foundry-agents").translator, FoundryAgent)
    assert model_from_env("foundry").translator is not None and model_from_env("offline").name == "offline"
