"""
The smart lane: Statistician (code, upstream) → Analyst (LLM) → Fact-checker (code) → Narrator (LLM).

    async def run_workflow(moment, factsheet, on_update, *, generation=0, model=None) -> Insight

- `on_update(insight)` is called for every intermediate state: 'analysing', then
  'streaming' with growing text. The final Insight is returned (phase 'done').
- The workflow owns its timeout (DEADLINE_S) and always returns an Insight: when
  the model fails or is too slow you get status 'fallback' with template text.
- Every number in the final text is backed by a fact in the FactSheet.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import time
from typing import Awaitable, Callable

from .checker import check_claims, check_text, unknown_names
from .llm import ModelClient, model_from_env
from .models import Claim, FactSheet, Insight, Moment, RejectedClaim
from .prompts import analyst_prompt, narrator_prompt

DEADLINE_S = float(os.getenv("AGENT_DEADLINE_S", "6"))
MAX_EVIDENCE = 4

OnUpdate = Callable[[Insight], Awaitable[None] | None]

INSIGHT_TYPE = {
    "goal": "goal",
    "red_card": "card",
    "yellow_card": "card",
    "big_chance": "bigchance",
    "tactical_change": "momentum",
    "update": "update",
    "full_time": "fulltime",
}

_default_model: ModelClient | None = None


def default_model() -> ModelClient:
    global _default_model
    if _default_model is None:
        _default_model = model_from_env()
    return _default_model


async def _emit(on_update: OnUpdate | None, insight: Insight) -> None:
    if on_update is None:
        return
    r = on_update(insight)
    if inspect.isawaitable(r):
        await r


def _base(moment: Moment, sheet: FactSheet, generation: int) -> Insight:
    s = sheet.match_state
    return Insight(
        id=f"i-{moment.moment_id}",
        t=moment.t,
        minute=moment.minute,
        moment_id=moment.moment_id,
        type=INSIGHT_TYPE[moment.kind],
        card="red" if moment.kind == "red_card" else "yellow" if moment.kind == "yellow_card" else None,
        team=moment.team,
        text="",
        phase="analysing",
        generation=generation,
        analyst_stats=[
            {"k": "Possession", "v": f"{round(s.possession[0])}–{round(s.possession[1])}"},
            {"k": "xG", "v": f"{s.xg[0]:.2f}–{s.xg[1]:.2f}"},
            {"k": "Shots", "v": f"{s.shots[0]}–{s.shots[1]}"},
        ],
    )


def _evidence(sheet: FactSheet, fact_ids: list[str]) -> list[str]:
    seen, out = set(), []
    for fid in fact_ids:
        f = sheet.fact(fid)
        if f and fid not in seen:
            seen.add(fid)
            out.append(f.text)
    return out[:MAX_EVIDENCE]


def template_text(sheet: FactSheet) -> str:
    """Fallback text: the headline plus the first fact. No model involved."""
    first = sheet.facts[0].text if sheet.facts else ""
    return f"{sheet.moment.headline}. {first}".strip().rstrip(".") + "."


async def run_workflow(
    moment: Moment,
    factsheet: FactSheet,
    on_update: OnUpdate | None = None,
    *,
    generation: int = 0,
    model: ModelClient | None = None,
    deadline_s: float | None = None,
) -> Insight:
    model = model or default_model()
    base = _base(moment, factsheet, generation)
    start = time.perf_counter()
    tokens = 0
    await _emit(on_update, base)

    async def pipeline() -> Insight:
        nonlocal tokens
        # 1. Analyst: structured claims with fact ids
        draft, used = await model.draft(factsheet, analyst_prompt(factsheet))
        tokens += used or 0

        # 2. Fact-checker (code)
        accepted, rejected = check_claims(draft.claims, factsheet)
        if not accepted:
            raise NoUsableClaims(rejected)

        # 3. Narrator: stream the text
        text = ""
        async for chunk in model.narrate(factsheet, accepted, narrator_prompt(factsheet, accepted)):
            text += chunk
            await _emit(on_update, base.model_copy(update={"phase": "streaming", "text": text.strip()}))
        text = _undouble(" ".join(text.split()))

        # 4. Check the Narrator too: no numbers or names that the accepted claims do not back
        cited = sorted({fid for c in accepted for fid in c.fact_ids})
        extra = check_text(text, factsheet, cited)
        names = unknown_names(text, factsheet, accepted)
        if extra or names or not text:
            if extra:
                reason = f"Narrator added unbacked number(s): {', '.join(f'{n:g}' for n in extra)}"
            elif names:
                reason = f"Narrator added name(s) not in the checked claims: {', '.join(names)}"
            else:
                reason = "Narrator returned no text"
            rejected.append(RejectedClaim(text=text or "(empty)", reason=reason, fact_ids=cited))
            text = " ".join(c.text for c in accepted)

        status = "corrected" if rejected else "checked"
        return base.model_copy(update={
            "phase": "done",
            "text": text,
            "status": status,
            "evidence": _evidence(factsheet, cited),
            "cited_fact_ids": cited,
            "rejected_claims": rejected,
            "claim": rejected[0].text if rejected else None,
        })

    try:
        insight = await asyncio.wait_for(pipeline(), timeout=deadline_s or DEADLINE_S)
    except asyncio.TimeoutError:
        insight = _fallback(base, factsheet, f"Model timed out after {deadline_s or DEADLINE_S:g} s")
    except NoUsableClaims as e:
        insight = _fallback(base, factsheet, "No claim passed the fact-check", e.rejected)
    except Exception as e:  # model or network error: never break the match
        insight = _fallback(base, factsheet, f"Model error: {type(e).__name__}")

    insight = insight.model_copy(update={
        "latency_ms": round((time.perf_counter() - start) * 1000),
        "tokens": tokens or None,
    })
    await _emit(on_update, insight)
    return insight


def _undouble(text: str) -> str:
    """Safety net: 'abc abc' -> 'abc' (a stream that repeated its full text at the end)."""
    half = len(text) // 2
    for cut in (half, half + 1, half - 1):
        a, b = text[:cut].strip(), text[cut:].strip()
        if a and a == b:
            return a
    return text


class NoUsableClaims(Exception):
    def __init__(self, rejected: list[RejectedClaim]):
        super().__init__("no usable claims")
        self.rejected = rejected


def _fallback(base: Insight, sheet: FactSheet, reason: str, rejected: list[RejectedClaim] | None = None) -> Insight:
    ids = [f.fact_id for f in sheet.facts[:1]]
    return base.model_copy(update={
        "phase": "done",
        "status": "fallback",
        "text": template_text(sheet),
        "fallback_reason": reason,
        "evidence": _evidence(sheet, ids),
        "cited_fact_ids": ids,
        "rejected_claims": rejected or [],
    })


__all__ = ["run_workflow", "template_text", "Claim"]
