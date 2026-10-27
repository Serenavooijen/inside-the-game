"""
Tactics per club: "How to beat {opponent}" (PERSPECTIVES_ENABLED=1).

    await run_perspective(sheet, team, model=...) -> Perspective

The neutral card stays as it is. Per club the Scout writes a variant on the same TacticalFactSheet: 1-2 levers,
each an observation about the opponent (factual, with fact ids), the consequence, and what this club's staff
should do. The perspective instruction goes in the prompt, not in the agent's fixed instructions, so the
hosted itg-scout stays as it is; the output schema is the Scout's own (ScoutDraft).

Every lever goes through the same check_observations as the neutral card (numbers, names, game state,
direction). A lever must be about the opponent and keep its advice. "What {opponent} changed today" is made
by the code from the opponent's facts that compare with the cup match, labelled changed or same. A variant
that fails, or comes too late, is "rejected" with a reason; the UI then shows the neutral card.
"""

from __future__ import annotations

import asyncio
import os
import time

from app.contracts import Perspective, PerspectiveChange, PerspectiveLever, TacticalFactSheet

from .deadline import within
from .llm import ModelClient
from .playbook import compare_from_text
from .prompts import scout_prompt

PERSPECTIVE_DEADLINE_S = float(os.getenv("PERSPECTIVE_DEADLINE_S", os.getenv("SCOUT_DEADLINE_S", "15")))
MAX_LEVERS = 2
MAX_CHANGES = 3

# At most 3 Scout calls at once (neutral + both clubs), across the lanes: they share one model quota.
_slots: asyncio.Semaphore | None = None


def scout_slots() -> asyncio.Semaphore:
    global _slots
    if _slots is None:
        _slots = asyncio.Semaphore(int(os.getenv("SCOUT_CONCURRENCY", "3")))
    return _slots


def perspectives_enabled() -> bool:
    return os.getenv("PERSPECTIVES_ENABLED", "").lower() in ("1", "true", "yes", "on")


def perspective_prompt(sheet: TacticalFactSheet, team: str) -> str:
    """The Scout's normal prompt, plus who it is advising. The observation stays about the opponent and factual."""
    opp = sheet.away if team == sheet.home else sheet.home
    club, other = sheet.team_names[team], sheet.team_names[opp]
    return scout_prompt(sheet) + (
        f"\n\nPerspective: you advise the coaching staff of {club} (team id {team}). Write 1 or 2 observations, "
        f"each about {other} (team \"{opp}\"), on how {club} can beat them:\n"
        f"- observation: what {other} do, factual, from the facts about {other}; never advice in the observation;\n"
        f"- consequence: what that means for {club};\n"
        f"- coach_action: what {club} should do about it (never \"\"). Name {club}; never \"we\" or \"our\".\n"
        f"All other rules stay the same.")


def changes_today(sheet: TacticalFactSheet, opponent: str) -> list[PerspectiveChange]:
    """What the opponent changed against the cup match: their facts that compare with it, made by the code."""
    out = []
    for f in sheet.facts:
        if f.team != opponent or f.metric == "game_state":
            continue
        label = compare_from_text(f)
        # "same" only where the code compares the values itself (the build-up shape); elsewhere a fact without
        # "up/down" may still differ from the cup match ("centre 71%; cup match: centre 34%"), so it is left out
        if label == "changed" or (label == "same" and f.concept == "B6"):
            out.append(PerspectiveChange(text=f.text, fact_ids=[f.fact_id], label=label))
    out.sort(key=lambda c: c.label != "changed")            # changes first
    return out[:MAX_CHANGES]


async def run_perspective(sheet: TacticalFactSheet, team: str, *, model: ModelClient,
                          deadline_s: float | None = None) -> tuple[Perspective, int | None, int]:
    """(the checked variant or a rejected one with the reason, tokens, latency in ms)."""
    from .scout import check_observations      # scout imports this module

    opp = sheet.away if team == sheet.home else sheet.home
    deadline = deadline_s or PERSPECTIVE_DEADLINE_S
    start = time.perf_counter()
    ms = lambda: round((time.perf_counter() - start) * 1000)  # noqa: E731
    scout = getattr(model, "scout", None)
    if scout is None:
        return Perspective(status="rejected", reason=f"No Scout in the {model.name} set-up"), None, 0

    async def call():
        async with scout_slots():
            return await scout(sheet, perspective_prompt(sheet, team))

    try:
        draft, tokens = await within(call(), deadline)
    except TimeoutError:
        return Perspective(status="rejected", reason=f"Perspective timed out after {deadline:g} s"), None, ms()
    except asyncio.CancelledError:
        raise
    except Exception as e:      # model or network error: the neutral card stays
        return Perspective(status="rejected", reason=f"Scout error: {type(e).__name__}"), None, ms()

    accepted, rejected = check_observations(draft.observations, sheet)
    levers = [PerspectiveLever(observation=o.observation, fact_ids=o.fact_ids, consequence=o.consequence,
                               coach_action=o.coach_action, compare_to_cup=o.compare_to_cup)
              for o in accepted if o.team == opp and o.coach_action][:MAX_LEVERS]
    if not levers:
        reason = rejected[0].reason if rejected else f"No lever about {sheet.team_names[opp]} with advice"
        return Perspective(status="rejected", reason=reason), tokens, ms()
    return Perspective(status="checked", levers=levers, changes=changes_today(sheet, opp)), tokens, ms()


async def run_perspectives(sheet: TacticalFactSheet, *, model: ModelClient, deadline_s: float | None = None
                           ) -> tuple[dict[str, Perspective], int, int]:
    """Both clubs in parallel: ({team: Perspective}, total tokens, latency in ms)."""
    start = time.perf_counter()
    teams = [sheet.home, sheet.away]
    done = await asyncio.gather(*(run_perspective(sheet, t, model=model, deadline_s=deadline_s) for t in teams))
    return ({t: p for t, (p, _, _) in zip(teams, done)}, sum(tok or 0 for _, tok, _ in done),
            round((time.perf_counter() - start) * 1000))
