"""
Tests for the agent workflow. No token or network needed.

    cd backend
    uv run pytest tests/agents -q
"""

from __future__ import annotations

import asyncio
import glob
import json
import os

import pytest

from app.agents.checker import check_claim
from app.agents.llm import AgentFrameworkModel, OfflineModel
from app.agents.models import Claim, FactSheet
from app.agents.workflow import run_workflow

from . import fake_openai

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FIXTURES = sorted(glob.glob(os.path.join(ROOT, "fixtures", "moments", "*.json")))


def sheet(moment_id: str = "goal-24") -> FactSheet:
    path = os.path.join(ROOT, "fixtures", "moments", f"{moment_id}.json")
    return FactSheet.model_validate(json.load(open(path, encoding="utf-8")))


# ---------------------------------------------------------------- checker


def test_checker_accepts_numbers_from_cited_facts():
    s = sheet()
    assert check_claim(Claim(text="The shot was worth 0.41 xG from 10.9 m.", fact_ids=["F1", "F2"]), s) is None


def test_checker_rejects_a_wrong_number():
    s = sheet()
    r = check_claim(Claim(text="The shot was worth 0.61 xG.", fact_ids=["F1"]), s)
    assert r is not None and "0.61" in r.reason


def test_checker_rejects_a_number_from_an_uncited_fact():
    s = sheet()
    r = check_claim(Claim(text="The shot came from 10.9 m.", fact_ids=["F1"]), s)
    assert r is not None


def test_checker_rejects_unknown_or_missing_facts():
    s = sheet()
    assert check_claim(Claim(text="Great goal.", fact_ids=[]), s) is not None
    assert check_claim(Claim(text="Great goal.", fact_ids=["F99"]), s) is not None


# ---------------------------------------------------------------- workflow, offline


@pytest.mark.parametrize("path", FIXTURES, ids=[os.path.basename(p) for p in FIXTURES])
def test_every_fixture_gives_a_checked_insight_offline(path):
    s = FactSheet.model_validate(json.load(open(path, encoding="utf-8")))
    phases = []
    insight = asyncio.run(run_workflow(s.moment, s, lambda i: phases.append(i.phase), model=OfflineModel(), generation=3))
    assert insight.status == "checked"
    assert insight.phase == "done" and phases[0] == "analysing" and "streaming" in phases and phases[-1] == "done"
    assert insight.text and insight.evidence and insight.generation == 3
    out = insight.to_json()
    assert "momentId" in out and "citedFactIds" in out  # camelCase for the frontend


# ---------------------------------------------------------------- Agent Framework against a fake OpenAI server


@pytest.fixture(scope="module")
def server():
    url, srv = fake_openai.start()
    yield url
    srv.shutdown()


def af_model(url: str) -> AgentFrameworkModel:
    return AgentFrameworkModel(name="fake", base_url=url, api_key="test", analyst_model="analyst", narrator_model="narrator")


def test_agent_framework_path_checked(server):
    fake_openai.STATE.update(wrong=False, slow_s=0)
    s = sheet()
    updates = []
    insight = asyncio.run(run_workflow(s.moment, s, updates.append, model=af_model(server)))
    assert insight.status == "checked", insight
    assert "0.41" in insight.text
    assert any(u.phase == "streaming" for u in updates)
    assert insight.tokens == 160
    analyst_call = next(r for r in fake_openai.STATE["requests"] if r.get("response_format"))
    assert analyst_call["model"] == "analyst"


def test_agent_framework_wrong_number_is_corrected(server):
    fake_openai.STATE.update(wrong=True, slow_s=0)
    s = sheet()
    insight = asyncio.run(run_workflow(s.moment, s, None, model=af_model(server)))
    assert insight.status == "corrected"
    assert insight.rejected_claims and "9.99" in insight.rejected_claims[0].text
    assert "9.99" not in insight.text


def test_timeout_gives_fallback(server):
    fake_openai.STATE.update(wrong=False, slow_s=1.5)
    s = sheet()
    insight = asyncio.run(run_workflow(s.moment, s, None, model=af_model(server), deadline_s=0.5))
    fake_openai.STATE.update(slow_s=0)
    assert insight.status == "fallback"
    assert "timed out" in (insight.fallback_reason or "")
    assert insight.text.startswith("Goal Northgate")


# ---------------------------------------------------------------- Foundry set-ups (no network: construction and parsing only)


class _Resp:
    def __init__(self, text, value=None):
        self.text, self.value = text, value


class _Upd:
    def __init__(self, text):
        self.text = text


class _HostedAnalyst:
    """Behaves like a FoundryAgent prompt agent: schema lives in Foundry, JSON comes back as text."""

    def __init__(self):
        self.options_seen = "unset"

    async def run(self, prompt, options=None):
        self.options_seen = options
        return _Resp('{"claims":[{"text":"Shot xG 0.41.","fact_ids":["F1"]}]}')


class _HostedNarrator:
    def run(self, prompt, stream=False):
        async def gen():
            for w in ["The", " shot", " was", " worth", " 0.41", " xG."]:
                yield _Upd(w)
        return gen()


def test_hosted_agents_path_parses_json_text_and_sends_no_schema():
    from app.agents.llm import AgentPairModel

    analyst = _HostedAnalyst()
    model = AgentPairModel(name="foundry-agents", analyst=analyst, narrator=_HostedNarrator(), pass_response_format=False)
    s = sheet()
    insight = asyncio.run(run_workflow(s.moment, s, None, model=model))
    assert insight.status == "checked" and insight.text == "The shot was worth 0.41 xG."
    assert analyst.options_seen is None


def test_foundry_builders_construct_without_network():
    from azure.core.credentials import AccessToken

    from app.agents.llm import foundry_code_agents, foundry_hosted_agents

    class Cred:
        scopes: list = []

        async def get_token(self, *a, **k):
            Cred.scopes.extend(a)
            return AccessToken("x", 9999999999)

        async def close(self):
            pass

    ep = "https://example.services.ai.azure.com/api/projects/itg"
    code = foundry_code_agents(ep, "gpt-4.1-mini", "gpt-4.1-nano", credential=Cred())
    hosted = foundry_hosted_agents(ep, ("itg-analyst", "1"), ("itg-narrator", "1"), credential=Cred())
    assert code.pass_response_format and not hosted.pass_response_format
    from agent_framework.foundry import FoundryAgent

    assert isinstance(hosted.analyst, FoundryAgent) and isinstance(hosted.narrator, FoundryAgent)
    asyncio.run(code.warmup())
    assert "https://ai.azure.com/.default" in Cred.scopes


# ---------------------------------------------------------------- narrator safety nets


def test_number_words_are_checked_too():
    from app.agents.checker import check_text

    s = sheet()
    assert check_text("One of the better chances, worth 0.41 xG.", s, ["F1"]) == []
    assert check_text("He scored from twenty-five metres.", s, ["F1"]) == [25.0]


def test_narrator_may_not_add_names():
    from app.agents.checker import unknown_names

    s = sheet()
    claims = [Claim(text="Duarte's long pass set up the shot.", fact_ids=["F3"])]
    assert unknown_names("Adeyemi-Clarke scores after Duarte's long pass. Kingsbridge are behind.", s, claims) == []
    assert unknown_names("Duarte found Smith, and Northgate lead.", s, claims) == ["Smith"]
    # a capitalised first word is not a name, a possessive at the start still is
    assert unknown_names("Following the long pass, Duarte's ball found the striker.", s, claims) == []
    assert unknown_names("Smith's run opened it up after Duarte's pass.", s, claims) == ["Smith"]


def test_stream_that_repeats_its_full_text_is_not_doubled():
    from app.agents.llm import AgentPairModel

    class Narrator:
        def run(self, prompt, stream=False):
            async def gen():
                for w in ["The", " shot", " was", " worth", " 0.41", " xG."]:
                    yield _Upd(w)
                yield _Upd("The shot was worth 0.41 xG.")  # full text again, as Foundry sends it

            return gen()

    model = AgentPairModel(name="x", analyst=_HostedAnalyst(), narrator=Narrator(), pass_response_format=False)
    s = sheet()
    insight = asyncio.run(run_workflow(s.moment, s, None, model=model))
    assert insight.text == "The shot was worth 0.41 xG."


# ---------------------------------------------------------------- any teams, not only kba/ngr


def test_other_teams_work_end_to_end():
    from app.agents.prompts import analyst_prompt

    s = sheet()
    raw = s.model_dump(by_alias=True)
    raw["teamNames"] = {"hv": "Harlow Vale", "su": "Saltmarsh United"}
    raw["moment"]["team"] = "su"
    other = FactSheet.model_validate(raw)
    assert "Score: Harlow Vale 0-1 Saltmarsh United" in analyst_prompt(other)
    insight = asyncio.run(run_workflow(other.moment, other, None, model=OfflineModel()))
    assert insight.team == "su" and insight.to_json()["team"] == "su"
