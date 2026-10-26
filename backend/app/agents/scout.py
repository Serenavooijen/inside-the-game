"""
The Scout: Tactician (code, upstream) → Scout (LLM) → Fact-checker (code).

    async def run_scout(sheet, on_update, *, generation=0, model=None) -> Insight   # type "tactics"

- Input is a TacticalFactSheet: the tactical facts of one window plus the cup baseline.
- Output: 2-3 checked observations, each with a consequence and an optional coach action.
- The checker is the gatekeeper:
    observation              check_claim: every number must be in a cited fact;
    consequence, coach action check_text + unknown_names: no numbers or names beyond the
                             observation and its facts (the concept names are allowed).
  A rejected observation is left out with its reason (status "corrected"); a coach action
  that fails is dropped on its own. compare_to_cup is reset to "n/a" when no cited fact
  mentions the cup match.
- Own deadline (SCOUT_DEADLINE_S, default 15 s); a timeout, an error or no usable
  observation gives the template observations (status "fallback"). Never raises.
"""

from __future__ import annotations

import asyncio
import os
import re
import time

from app.contracts import Heatmap, Player, TacticalFactSheet, TacticalObservation

from .checker import check_claim, check_text, unknown_names
from .llm import ModelClient
from .models import Claim, Insight, RejectedClaim, ScoutObservationDraft
from .playbook import compare_from_text, concept_terms, template_observations
from .prompts import scout_prompt
from .workflow import OnUpdate, _emit, default_model

SCOUT_DEADLINE_S = float(os.getenv("SCOUT_DEADLINE_S", "15"))
MAX_OBSERVATIONS = 3
MAX_EVIDENCE = 6
# "the 6", "their 8s", "a back three", "three at the back": football terms, not statistics.
# Hidden from the number check only.
ROLE = re.compile(r"\b(the|a|an|their|our|its|his|her|both|two|new|opposing|own)( \w+)? (6|8|10)s?\b", re.I)
LINE_TERM = re.compile(r"\b(back|front) (two|three|four|five)\b|\b(two|three|four|five) at the back\b"
                       r"|\b(two|three|four|five)-man\b", re.I)


def _roles_out(text: str) -> str:
    text = ROLE.sub(lambda m: f"{m.group(1)}{m.group(2) or ''} role", text)
    return LINE_TERM.sub("line-term", text)


def insight_id(sheet: TacticalFactSheet) -> str:
    return f"i-tac-{sheet.trigger}-{round(sheet.window.to_t)}"


def check_observation(o: ScoutObservationDraft | TacticalObservation, sheet: TacticalFactSheet
                      ) -> tuple[TacticalObservation | None, list[RejectedClaim]]:
    """The checked observation (or None) and what was rejected, with the reason."""
    rejected: list[RejectedClaim] = []
    r = check_claim(Claim(text=_roles_out(o.observation), fact_ids=o.fact_ids), sheet)
    if r:
        r = r.model_copy(update={"text": o.observation})
    if r:
        return None, [r]
    facts = [sheet.fact(fid) for fid in o.fact_ids]
    # Interpretation may only lean on the observation and its facts.
    known = [Claim(text=o.observation, fact_ids=o.fact_ids), *(Claim(text=f.text, fact_ids=[f.fact_id]) for f in facts)]
    terms = concept_terms()

    def fails(text: str, part: str) -> str | None:
        extra = check_text(_roles_out(text), sheet, o.fact_ids)
        if extra:
            return f"{part} added number(s) not in the observation's facts: {', '.join(f'{n:g}' for n in extra)}"
        names = unknown_names(text, sheet, known, terms)
        if names:
            return f"{part} added name(s) not in the observation: {', '.join(names)}"
        return None

    consequence = (o.consequence or "").strip()
    reason = fails(consequence, "Consequence") if consequence else "No consequence given"
    if reason:
        return None, [RejectedClaim(text=f"{o.observation} Consequence: {consequence or '(empty)'}", reason=reason,
                                    fact_ids=o.fact_ids)]
    coach = (o.coach_action or "").strip() or None
    if coach and (reason := fails(coach, "Coach action")):
        rejected.append(RejectedClaim(text=f"Coach action: {coach}", reason=reason + " (dropped)", fact_ids=o.fact_ids))
        coach = None

    cup_facts = [f for f in facts if f.fact_id.startswith("C") or compare_from_text(f) != "n/a"]
    compare = o.compare_to_cup if cup_facts else "n/a"
    team = o.team if o.team in (sheet.home, sheet.away) else next((f.team for f in facts if f.team), None)
    return TacticalObservation(observation=o.observation.strip(), fact_ids=list(o.fact_ids), consequence=consequence,
                               coach_action=coach, compare_to_cup=compare, team=team), rejected


def check_observations(drafts: list, sheet: TacticalFactSheet) -> tuple[list[TacticalObservation], list[RejectedClaim]]:
    accepted, rejected = [], []
    for d in drafts:
        ok, rej = check_observation(d, sheet)
        rejected += rej
        if ok and len(accepted) < MAX_OBSERVATIONS:
            accepted.append(ok)
    return accepted, rejected


def _evidence(sheet: TacticalFactSheet, observations: list[TacticalObservation]) -> tuple[list[str], list[str]]:
    ids = list(dict.fromkeys(fid for o in observations for fid in o.fact_ids))
    return [sheet.fact(fid).text for fid in ids if sheet.fact(fid)][:MAX_EVIDENCE], ids


def _done(base: Insight, sheet: TacticalFactSheet, observations: list[TacticalObservation], **update) -> Insight:
    evidence, ids = _evidence(sheet, observations)
    team = next((o.team for o in observations if o.team), None)
    return base.model_copy(update={
        "phase": "done", "observations": observations, "team": team,
        "text": " ".join(o.observation for o in observations), "evidence": evidence, "cited_fact_ids": ids, **update,
    })


async def run_scout(
    sheet: TacticalFactSheet,
    on_update: OnUpdate | None = None,
    *,
    generation: int = 0,
    model: ModelClient | None = None,
    deadline_s: float | None = None,
    heatmap: Heatmap | None = None,
    build_up: list[Player] | None = None,
) -> Insight:
    model = model or default_model()
    deadline = deadline_s or SCOUT_DEADLINE_S
    base = Insight(
        id=insight_id(sheet), t=sheet.window.to_t, minute=sheet.minute, type="tactics", trigger=sheet.trigger,
        window=sheet.window, text="", phase="analysing", generation=generation,
        heatmap=heatmap, build_up=build_up or None,
    )
    start = time.perf_counter()
    tokens = 0
    await _emit(on_update, base)

    async def pipeline() -> Insight:
        nonlocal tokens
        scout = getattr(model, "scout", None)
        if scout is None:
            raise LookupError(f"model {getattr(model, 'name', '?')} has no Scout")
        draft, used = await scout(sheet, scout_prompt(sheet))
        tokens += used or 0
        accepted, rejected = check_observations(draft.observations, sheet)
        if not accepted:
            raise NoUsableObservations(rejected)
        dropped = [r for r in rejected if not r.reason.endswith("(dropped)")]
        return _done(base, sheet, accepted, status="corrected" if rejected else "checked", rejected_claims=rejected,
                     claim=dropped[0].text if dropped else (rejected[0].text if rejected else None))

    try:
        insight = await asyncio.wait_for(pipeline(), timeout=deadline)
    except asyncio.TimeoutError:
        insight = _fallback(base, sheet, f"Scout timed out after {deadline:g} s")
    except NoUsableObservations as e:
        insight = _fallback(base, sheet, "No observation passed the fact-check", e.rejected)
    except asyncio.CancelledError:
        raise
    except LookupError as e:
        insight = _fallback(base, sheet, str(e))
    except Exception as e:  # model or network error: never break the match
        insight = _fallback(base, sheet, f"Scout error: {type(e).__name__}")

    insight = insight.model_copy(update={"latency_ms": round((time.perf_counter() - start) * 1000), "tokens": tokens or None})
    await _emit(on_update, insight)
    return insight


class NoUsableObservations(Exception):
    def __init__(self, rejected: list[RejectedClaim]):
        super().__init__("no usable observations")
        self.rejected = rejected


def _fallback(base: Insight, sheet: TacticalFactSheet, reason: str, rejected: list[RejectedClaim] | None = None) -> Insight:
    """Template observations (facts + playbook), checked like the model's, so even the fallback is backed."""
    observations, _ = check_observations(template_observations(sheet, n=2), sheet)
    return _done(base, sheet, observations, status="fallback", fallback_reason=reason, rejected_claims=rejected or [])
