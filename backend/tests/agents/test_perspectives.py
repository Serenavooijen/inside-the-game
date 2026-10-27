"""Tactics per club: 'How to beat {opponent}', checked like the neutral card, never in place of it."""

from __future__ import annotations

import asyncio

from app.agents.models import ScoutDraft, ScoutObservationDraft
from app.agents.perspectives import changes_today, perspective_prompt, run_perspective, run_perspectives
from app.bus import EventBus
from app.contracts import Insight, Perspective, PerspectiveLever, TacticalObservation
from app.fixture import MATCH_ID, GeneratorSource
from app.simulator import Simulator

from .test_scout import obs, sheet


class ClubScout:
    """A Scout that answers per perspective: the prompt says which club it advises."""

    name = "club-scout"

    def __init__(self, per_club: dict[str, list[ScoutObservationDraft]], delay_s: float = 0.0):
        self.per_club, self.delay_s, self.prompts = per_club, delay_s, []

    async def scout(self, sheet, prompt):
        self.prompts.append(prompt)
        await asyncio.sleep(self.delay_s)
        club = "kba" if "(team id kba)" in prompt else "ngr"
        return ScoutDraft(observations=self.per_club.get(club, [])), 200


# Northgate's view: a lever about Kingsbridge (T2); Kingsbridge's view: a lever about Northgate (T1).
ABOUT_KBA = obs(observation="Kingsbridge defended in a low block, their last line 22 m from their own goal.", fact_ids=["T2"],
                team="kba", consequence="Space opens between the lines in front of the block.",
                coach_action="Northgate should play into the half-spaces and shoot from distance.", compare_to_cup="n/a")
ABOUT_NGR = obs(coach_action="Kingsbridge should press the centre-backs with both strikers.")


def test_the_prompt_names_the_club_and_the_opponent_and_keeps_the_scout_rules():
    p = perspective_prompt(sheet(), "ngr")
    assert "advise the coaching staff of Northgate" in p and "each about Kingsbridge" in p
    assert p.startswith("Window 65'–70'")                    # the normal Scout prompt comes first


def test_both_clubs_get_a_checked_variant_on_the_same_facts():
    found, tokens, _ = asyncio.run(run_perspectives(sheet(), model=ClubScout({"ngr": [ABOUT_KBA], "kba": [ABOUT_NGR]})))
    assert found["ngr"].status == "checked" and found["ngr"].levers[0].fact_ids == ["T2"]
    assert found["kba"].status == "checked" and found["kba"].levers[0].coach_action.startswith("Kingsbridge should")
    assert tokens == 400
    # what Northgate changed today, made by the code: the fact that compares with the cup match, labelled
    assert [(c.fact_ids, c.label) for c in found["kba"].changes] == [(["T1"], "changed")]


def test_a_variant_with_a_made_up_number_is_rejected_and_the_other_stays():
    wrong = ABOUT_KBA.model_copy(update={"observation": "Kingsbridge defended in a low block, their last line 31 m from their own goal."})
    found, _, _ = asyncio.run(run_perspectives(sheet(), model=ClubScout({"ngr": [wrong], "kba": [ABOUT_NGR]})))
    assert found["ngr"].status == "rejected" and "31" in found["ngr"].reason and found["ngr"].levers == []
    assert found["kba"].status == "checked"


def test_a_lever_must_be_about_the_opponent_and_keep_its_advice():
    own = ABOUT_NGR.model_copy(update={"coach_action": "Northgate should keep the 6 high."})   # about Northgate itself
    p, _, _ = asyncio.run(run_perspective(sheet(), "ngr", model=ClubScout({"ngr": [own]})))
    assert p.status == "rejected" and "Kingsbridge" in p.reason


def test_a_timeout_rejects_the_variant():
    p, _, _ = asyncio.run(run_perspective(sheet(), "ngr", model=ClubScout({"ngr": [ABOUT_KBA]}, delay_s=5), deadline_s=0.2))
    assert p.status == "rejected" and p.reason == "Perspective timed out after 0.2 s"


def test_changes_today_only_from_facts_that_compare_with_the_cup():
    assert changes_today(sheet(), "kba") == []                # no Kingsbridge fact mentions the cup match


# ------------------------------------------------------------------ on the stream (simulator)

def tactics_card(generation: int) -> Insight:
    o = TacticalObservation(observation="Kingsbridge defended in a low block.", fact_ids=["T2"], consequence="Space between lines.",
                            team="kba")
    return Insight(id="i-tac-interval-4200", t=4200, minute="70", type="tactics", text=o.observation, status="checked",
                   observations=[o], generation=generation)


def with_perspectives(card: Insight) -> Insight:
    lever = PerspectiveLever(observation="Kingsbridge defended in a low block.", fact_ids=["T2"],
                             consequence="Space between lines.", coach_action="Northgate should play into the half-spaces.")
    return card.model_copy(update={"perspectives": {"ngr": Perspective(status="checked", levers=[lever]),
                                                    "kba": Perspective(status="rejected", reason="Perspective timed out after 15 s")}})


def run_sim(scenario):
    async def main():
        sim = Simulator(EventBus(maxsize=10_000), {MATCH_ID: GeneratorSource})
        await sim.load(MATCH_ID, "live")
        return await scenario(sim)
    return asyncio.run(main())


def test_the_variants_arrive_as_an_update_and_the_neutral_card_stays_intact():
    async def scenario(sim):
        card = tactics_card(sim.generation)
        sim._on_insight(card)
        sim._on_insight(with_perspectives(card))
        return sim.insights[card.id]

    got = run_sim(scenario)
    assert got.observations == tactics_card(0).observations and got.text == tactics_card(0).text   # neutral unchanged
    assert got.perspectives["ngr"].status == "checked" and got.perspectives["kba"].status == "rejected"


def test_variants_of_an_old_generation_are_dropped():
    async def scenario(sim):
        old = tactics_card(sim.generation)
        sim._on_insight(old)
        sim.seek(600)                                   # new generation
        sim._on_insight(with_perspectives(old))
        return sim.insights.get(old.id)

    assert run_sim(scenario) is None
