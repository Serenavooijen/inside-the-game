"""
The Scout: checked observations from a TacticalFactSheet. No token or network needed.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents.checker import unknown_names
from app.agents.llm import AgentFrameworkModel, AgentPairModel, OfflineModel
from app.agents.models import ScoutObservationDraft
from app.agents.playbook import concept_terms, concepts, one_liner
from app.agents.prompts import scout_prompt
from app.agents.scout import check_observation, run_scout
from app.contracts import Fact, MatchSnapshot, TacticalFactSheet, TacticalWindow

from . import fake_openai


def sheet() -> TacticalFactSheet:
    return TacticalFactSheet(
        window=TacticalWindow(from_t=3901, to_t=4200, label="65'–70'"), trigger="interval", minute="70",
        headline="Tactics 65'–70': Kingsbridge 1-1 Northgate", home="kba", away="ngr",
        team_names={"kba": "Kingsbridge", "ngr": "Northgate"},
        match_state=MatchSnapshot(score=(1, 1), players_on_pitch=(10, 11), possession=(45.0, 55.0), xg=(1.2, 0.9), shots=(9, 6)),
        facts=[
            Fact(fact_id="T1", text="Northgate's 6, Duarte (8), dropped between the centre-backs in 0% of 5 build-up phases "
                 "(cup match: 58%, down 58 points)", metric="dm_between_pct", value=0, team="ngr", concept="B1"),
            Fact(fact_id="T2", text="Kingsbridge defended in a low block: last line 22 m from their own goal, first line 44 m "
                 "(previous 5 minutes: 26 m)", metric="line_height_m", value=22, team="kba", concept="D1"),
            Fact(fact_id="T3", text="Northgate's attacks: left 34%, centre 58%, right 8%", metric="channel_centre_pct",
                 value=58, team="ngr", concept="P1"),
        ],
        baseline=[Fact(fact_id="C14", text="Cup match: Northgate's 6, Duarte (8), dropped between the centre-backs in 58% "
                       "of 97 build-up phases", metric="dm_between_pct", value=58, team="ngr", concept="B1")],
        concepts_fired=["B1", "D1", "P1"],
    )


def obs(**kw) -> ScoutObservationDraft:
    base = dict(observation="Northgate's 6 no longer drops in: 0% of 5 build-up phases, against 58% in the cup match.",
                fact_ids=["T1"], consequence="Northgate build with two at the back, so a two-man press can go man for man.",
                coach_action="Press the centre-backs with both strikers.", compare_to_cup="changed", team="ngr")
    return ScoutObservationDraft(**(base | kw))


# ---------------------------------------------------------------- playbook


def test_playbook_is_parsed_and_condensed():
    cs = concepts()
    assert len(cs) == 29 and cs["B1"].name.startswith("Back three via a dropping 6")
    line = one_liner("B1")
    assert line.startswith("B1 Back three") and "coach:" in line and "\n" not in line
    assert "lavolpiana" in concept_terms() and "ppda" in concept_terms()


def test_the_prompt_has_only_the_fired_concepts():
    p = scout_prompt(sheet())
    assert "B1 Back three" in p and "D1 Block height" in p and "P1 Overload" in p
    assert "B5" not in p and "Rules for the Scout" not in p
    assert "[T1] (ngr, B1)" in p and "[C14] (ngr, B1)" in p and "10 v 11" in p


# ---------------------------------------------------------------- checker


def test_a_backed_observation_passes():
    ok, rejected = check_observation(obs(), sheet())
    assert ok and not rejected and ok.compare_to_cup == "changed" and ok.team == "ngr"


def test_an_observation_with_a_wrong_number_is_left_out_with_a_reason():
    ok, rejected = check_observation(obs(observation="Northgate's 6 dropped in 12% of build-up phases."), sheet())
    assert ok is None and "12" in rejected[0].reason


def test_a_consequence_may_not_add_numbers_or_names():
    ok, rejected = check_observation(obs(consequence="That leaves 3 attackers against 2 defenders."), sheet())
    assert ok is None and rejected[0].reason.startswith("Consequence added number(s)")
    ok, rejected = check_observation(obs(consequence="So Halvorsen is free between the lines."), sheet())
    assert ok is None and "Halvorsen" in rejected[0].reason


def test_concept_names_are_no_invented_names():
    s = sheet()
    text = "A low block, the opposite of Gegenpressing, invites pressure; PPDA alone will not show it."
    assert unknown_names(text, s, [], concept_terms()) == []
    assert unknown_names(text, s, []) == ["Gegenpressing", "PPDA"]


def test_a_bad_coach_action_is_dropped_on_its_own():
    ok, rejected = check_observation(obs(coach_action="Put Rasmussen on the 6."), sheet())
    assert ok and ok.coach_action is None
    assert rejected and rejected[0].reason.endswith("(dropped)")


def test_compare_to_cup_needs_a_cup_fact():
    ok, _ = check_observation(obs(observation="Kingsbridge's last line is 22 m from their own goal.", fact_ids=["T2"],
                                  consequence="Kingsbridge defend deep and protect the box.", compare_to_cup="changed",
                                  team="kba"), sheet())
    assert ok and ok.compare_to_cup == "n/a"


# ---------------------------------------------------------------- workflow


def test_offline_scout_gives_checked_observations():
    phases = []
    insight = asyncio.run(run_scout(sheet(), lambda i: phases.append(i.phase), model=OfflineModel(), generation=4))
    assert phases == ["analysing", "done"]
    assert insight.status == "checked" and insight.type == "tactics" and insight.generation == 4
    assert insight.id == "i-tac-interval-4200" and insight.window.label == "65'–70'"
    assert 1 <= len(insight.observations) <= 3
    for o in insight.observations:
        assert o.consequence and set(o.fact_ids) <= {"T1", "T2", "T3", "C14"}
    data = insight.to_json()
    assert data["observations"][0]["compareToCup"] in ("same", "changed", "n/a") and "citedFactIds" in data


class _NoScout:
    name = "plain"

    async def draft(self, *a):  # pragma: no cover
        raise AssertionError


def test_a_model_without_a_scout_gives_the_fallback():
    insight = asyncio.run(run_scout(sheet(), None, model=_NoScout()))
    assert insight.status == "fallback" and insight.observations and "no Scout" in insight.fallback_reason


def test_a_pair_without_scout_agent_gives_the_fallback():
    model = AgentPairModel(name="foundry-agents", analyst=None, narrator=None, pass_response_format=False)
    insight = asyncio.run(run_scout(sheet(), None, model=model))
    assert insight.status == "fallback" and "NoScoutAgent" in insight.fallback_reason


class _SlowScout:
    name = "slow"

    async def scout(self, sheet, prompt):
        await asyncio.sleep(5)


def test_a_slow_scout_times_out_into_the_fallback():
    insight = asyncio.run(run_scout(sheet(), None, model=_SlowScout(), deadline_s=0.2))
    assert insight.status == "fallback" and "timed out" in insight.fallback_reason
    assert all(o.consequence for o in insight.observations)


# ---------------------------------------------------------------- Agent Framework against a fake OpenAI server


@pytest.fixture(scope="module")
def server():
    url, srv = fake_openai.start()
    yield url
    srv.shutdown()
    fake_openai.STATE["requests"].clear()   # the workflow tests look for the Analyst's request


def af_model(url: str):
    return AgentFrameworkModel(name="fake", base_url=url, api_key="test", analyst_model="analyst",
                               narrator_model="narrator", scout_model="scout")


def test_agent_framework_scout_checked(server):
    fake_openai.STATE.update(slow_s=0, scout_bad=False)
    insight = asyncio.run(run_scout(sheet(), None, model=af_model(server)))
    assert insight.status == "checked", insight.rejected_claims
    assert [o.fact_ids for o in insight.observations] == [["T1"], ["T2"]]
    assert insight.observations[0].compare_to_cup == "changed"     # T1 cites the cup match
    assert insight.observations[1].compare_to_cup == "n/a"         # T2 does not
    assert insight.tokens == 160
    call = next(r for r in fake_openai.STATE["requests"] if "observations" in str(r.get("response_format")))
    assert call["model"] == "scout"


def test_agent_framework_scout_bad_parts_are_corrected(server):
    fake_openai.STATE.update(slow_s=0, scout_bad=True)
    insight = asyncio.run(run_scout(sheet(), None, model=af_model(server)))
    fake_openai.STATE.update(scout_bad=False)
    assert insight.status == "corrected"
    assert [o.fact_ids for o in insight.observations] == [["T2"]]    # the observation with the bad consequence is gone
    assert insight.observations[0].coach_action is None             # the bad coach action is dropped
    reasons = [r.reason for r in insight.rejected_claims]
    assert any(r.startswith("Consequence added number(s)") for r in reasons)
    assert any("Rasmussen" in r for r in reasons)


def test_hosted_scout_is_built_only_with_a_version(monkeypatch):
    from agent_framework.foundry import FoundryAgent

    from app.agents.llm import model_from_env

    for k, v in {"FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/itg",
                 "FOUNDRY_ANALYST_AGENT_VERSION": "1", "FOUNDRY_NARRATOR_AGENT_VERSION": "1",
                 "AZURE_CREDENTIAL": "default"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("FOUNDRY_SCOUT_AGENT_VERSION", raising=False)
    assert model_from_env("foundry-agents").scout_agent is None      # the rest keeps working without it
    monkeypatch.setenv("FOUNDRY_SCOUT_AGENT_VERSION", "3")
    assert isinstance(model_from_env("foundry-agents").scout_agent, FoundryAgent)
