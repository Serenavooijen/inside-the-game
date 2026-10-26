"""
The Scout: checked observations from a TacticalFactSheet. No token or network needed.
"""

from __future__ import annotations

import asyncio
import re

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
    assert "- Back three via a dropping 6" in p and "- Block height" in p and "- Overload on one flank" in p
    assert "Direct build-up" not in p and "Rules for the Scout" not in p
    assert "(team ngr; Back three via a dropping 6" in p and "[C14] Cup match" in p and "10 v 11" in p
    # concept ids look like fact ids ("P1" vs "T1") and got cited as such: they are not in the prompt
    assert not re.search(r"\b[BPDTSG]\d\b", p.split("Facts:")[0].split("Concepts found:")[1])


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


def test_football_terms_are_no_numbers_but_statistics_are():
    s = sheet()
    ok, _ = check_observation(obs(consequence="Without the 6 in the last line there is no back three, so a two-man press works."), s)
    assert ok
    ok, rejected = check_observation(obs(consequence="Their 3 attackers face a back four."), s)
    assert ok is None and rejected[0].reason.endswith(": 3")


def test_tactical_vocabulary_passes_the_checks():
    ok, rejected = check_observation(obs(coach_action="Far-side full-back stays narrow; press with three up front."), sheet())
    assert ok and ok.coach_action and not rejected


def test_the_committed_scouting_report_is_backed_by_its_own_facts():
    """fixtures/scouting/kba-ngr-cup.json: every observation still passes the checker against the report's facts."""
    import json
    from pathlib import Path

    from app.contracts import ScoutingReport

    path = Path(__file__).resolve().parents[3] / "fixtures" / "scouting" / "kba-ngr-cup.json"
    report = ScoutingReport.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert 4 <= len(report.observations) <= 6 and all(f.fact_id.startswith("C") for f in report.facts)
    sheet = TacticalFactSheet(window=TacticalWindow(from_t=0, to_t=1, label="cup match"), trigger="scouting", minute="90",
                              headline=report.title, home=report.home, away=report.away,
                              team_names={"kba": "Kingsbridge", "ngr": "Northgate"}, facts=report.facts)
    for o in report.observations:
        ok, _ = check_observation(o, sheet)
        assert ok is not None, o.observation
    assert any(f.metric == "dm_between_pct" and f.team == "ngr" and f.value >= 40 for f in report.facts)


def test_the_threshold_filter_never_hides_a_change_from_the_cup():
    """A 0% dropping 6 is hidden as a plan, unless the cup match showed it: then it is the change."""
    from app.agents.playbook import template_observations, visible_to_scout

    def b1(text: str, value: float) -> Fact:
        return Fact(fact_id="T1", text=text, metric="dm_between_pct", value=value, team="ngr", concept="B1")

    changed = b1("Northgate's 6, Duarte (8), dropped between the centre-backs in 0% of 5 build-up phases "
                 "(cup match: 58%, down 58 points)", 0)
    never = b1("Northgate's 6, Duarte (8), dropped between the centre-backs in 5% of 9 build-up phases "
               "(cup match: 8%)", 5)
    alone = b1("Northgate's 6, Duarte (8), dropped between the centre-backs in 5% of 9 build-up phases", 5)
    assert visible_to_scout(changed) and not visible_to_scout(never) and not visible_to_scout(alone)

    s = sheet().model_copy(update={"facts": [changed]})
    [o] = template_observations(s)
    assert o.fact_ids == ["T1"] and o.compare_to_cup == "changed"
    assert "change from the cup plan" in o.consequence          # not the playbook's "dropping 6" consequence
    ok, _ = check_observation(o, s)
    assert ok is not None
    assert template_observations(sheet().model_copy(update={"facts": [never]})) == []


def test_the_report_tool_uses_the_same_rule():
    import tools.build_scouting_report as tool
    from app.agents.playbook import visible_to_scout

    assert tool.visible_to_scout is visible_to_scout


def test_claims_about_the_score_must_match_the_game_state_facts():
    from app.agents.checker import game_state_errors

    s = sheet().model_copy(update={"facts": [
        Fact(fact_id="T8", text="At 80': Kingsbridge 1-2 Northgate, 10 v 11 players on the pitch", metric="game_state",
             value="1-2", team="kba", concept="G3"),
        Fact(fact_id="T9", text="At 61' Northgate were level at 1-1, 11 v 11", metric="game_state", value="1-1",
             team="ngr", concept="G3"),
        *sheet().facts,
    ]})
    assert game_state_errors("Kingsbridge leads 2-1 with 10 men and press very intensely.", s) == ["Kingsbridge leading ('leads')"]
    assert game_state_errors("Northgate lead 2-1 against 10 men.", s) == []
    assert game_state_errors("Kingsbridge, trailing with 10 men, push their line up.", s) == []
    assert game_state_errors("Northgate changed shape while the game was tied 1-1.", s) == []     # the 61' fact
    assert game_state_errors("Northgate were trailing when they switched.", s) == ["Northgate trailing ('trailing')"]
    assert game_state_errors("Kingsbridge play with nine men.", s) == ["Kingsbridge with 9 men"]
    # space and causes are no score claims
    assert game_state_errors("Kingsbridge leave space behind; this leads to counters for Northgate.", s) == []
    ok, rejected = check_observation(obs(observation="Kingsbridge leads 2-1 and Northgate's 6 no longer drops in: 0% of 5 build-up phases.",
                                         fact_ids=["T8", "T1"]), s)
    assert ok is None and rejected[0].reason.startswith("Game state does not match the facts")


def test_the_deadline_does_not_wait_for_a_call_that_ignores_cancellation():
    """A model call stuck in its client once held a 15 s deadline for 727 s: the deadline must not wait for it."""
    import time

    class Stuck(OfflineModel):
        name = "stuck"

        async def scout(self, sheet, prompt):
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                await asyncio.sleep(2)          # unwinds slowly, like a hung HTTP client
                raise

    async def main():
        t0 = time.perf_counter()
        insight = await run_scout(sheet(), None, model=Stuck(), deadline_s=0.2)
        return insight, time.perf_counter() - t0

    insight, took = asyncio.run(main())
    assert insight.status == "fallback" and "timed out" in insight.fallback_reason
    assert took < 1.0
