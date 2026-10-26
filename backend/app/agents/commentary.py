"""
Narrator per minute: one short line of commentary (at most 25 words) for every match minute.

    async def run_commentary(sheet, claims, *, model, generation, source_insight_id) -> Commentary | None

- `sheet`: a small FactSheet from the Stats Engine for that minute (score, possession in the
  minute, the most important action) plus the fact lines behind the latest tactics card.
- `claims`: the checked observations of the latest tactics card (may be empty).
- The line goes through check_text and unknown_names, like the Narrator's text at a moment.
  Too long, rejected, empty, an error or too late: None. Rather a silent minute than an
  invented sentence.
"""

from __future__ import annotations

import asyncio
import os

from app.contracts import Commentary

from .checker import check_text, unknown_names
from .deadline import within
from .models import Claim, FactSheet
from .playbook import concept_terms

COMMENTARY_DEADLINE_S = float(os.getenv("COMMENTARY_DEADLINE_S", "5"))
MAX_WORDS = 25


def commentary_prompt(sheet: FactSheet, claims: list[Claim]) -> str:
    lines = [f"Minute {sheet.moment.minute}: {sheet.moment.headline}",
             "Write ONE sentence of live commentary, at most 25 words, from these facts and claims only.",
             "Facts:"]
    lines += [f"- {f.text}" for f in sheet.facts]
    if claims:
        lines.append("Checked claims from the latest tactical analysis:")
        lines += [f"- {c.text}" for c in claims]
    return "\n".join(lines)


def _template(sheet: FactSheet) -> str:
    """Offline: the minute's most important action, or the score line."""
    first = sheet.facts[0].text if sheet.facts else sheet.moment.headline
    return first.rstrip(".") + "."


def check_line(text: str, sheet: FactSheet, claims: list[Claim]) -> str | None:
    """The reason the line may not be shown, or None."""
    if not text:
        return "empty"
    if len(text.split()) > MAX_WORDS:
        return f"more than {MAX_WORDS} words"
    extra = check_text(text, sheet, [f.fact_id for f in sheet.facts])
    if extra:
        return f"unbacked number(s): {', '.join(f'{n:g}' for n in extra)}"
    sources = [*claims, *(Claim(text=f.text, fact_ids=[f.fact_id]) for f in sheet.facts)]
    names = unknown_names(text, sheet, sources, concept_terms())
    if names:
        return f"unknown name(s): {', '.join(names)}"
    return None


async def run_commentary(sheet: FactSheet, claims: list[Claim], *, model, generation: int = 0,
                         source_insight_id: str | None = None, deadline_s: float | None = None) -> Commentary | None:
    async def write() -> str:
        if getattr(model, "name", "") == "offline":
            return _template(sheet)
        text = ""
        async for chunk in model.narrate(sheet, claims, commentary_prompt(sheet, claims)):
            text += chunk
        return " ".join(text.split())

    try:
        text = await within(write(), deadline_s or COMMENTARY_DEADLINE_S)
    except asyncio.CancelledError:
        raise
    except Exception:          # timeout, model or network error: a silent minute
        return None
    if check_line(text, sheet, claims):
        return None
    return Commentary(t=sheet.moment.t, minute=sheet.moment.minute, text=text, source_insight_id=source_insight_id,
                      generation=generation)
