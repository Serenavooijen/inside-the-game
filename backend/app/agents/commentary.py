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
import re

from app.contracts import Commentary

from .checker import check_text, numbers_in, unknown_names
from .deadline import within
from .models import Claim, FactSheet
from .playbook import ACTIVE_FROM, concept_terms

COMMENTARY_DEADLINE_S = float(os.getenv("COMMENTARY_DEADLINE_S", "5"))
MAX_WORDS = 25


def commentary_prompt(sheet: FactSheet, claims: list[Claim]) -> str:
    lines = [f"Minute {sheet.moment.minute}: {sheet.moment.headline}",
             "Write ONE sentence of live commentary, at most 25 words, from these facts and claims only.",
             "Talk about today's match. Parts that name the cup match describe the earlier cup match, not today: "
             "use them only as an explicit comparison (\"in the cup match ...\"), never as something a team does today.",
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
    if reason := cup_as_today(text, sheet, claims):
        return reason
    sources = [*claims, *(Claim(text=f.text, fact_ids=[f.fact_id]) for f in sheet.facts)]
    names = unknown_names(text, sheet, sources, concept_terms())
    if names:
        return f"unknown name(s): {', '.join(names)}"
    return None


# Behaviour words per playbook concept. In a sentence that does not name the cup match they claim the team
# does it today, which needs today's fact for that concept above the concept's threshold.
BEHAVIOUR = {
    "B1": re.compile(r"\b(?:drop(?:s|ped|ping)? (?:in|between)|dropping (?:6|six)|back three|salida)\b", re.I),
    "B3": re.compile(r"\b(?:invert(?:s|ed|ing)?|(?:moves?|moved|moving|tucks?|tucked|tucking) inside)\b", re.I),
    "B5": re.compile(r"\b(?:long balls?|go(?:es|ing)? long|direct build-?up)\b", re.I),
    "T1": re.compile(r"\b(?:counter-?press(?:es|ed|ing)?|gegenpress(?:ing)?)\b", re.I),
}


def _without_cup(text: str) -> str:
    """The text without every bracketed part that names the cup match (nested brackets included)."""
    out, depth, start, keep = [], 0, 0, []
    for i, ch in enumerate(text):
        if ch == "(":
            if depth == 0:
                keep.append(text[start:i])
                start = i
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
            if depth == 0:
                group = text[start:i + 1]
                if "cup" not in group.lower():
                    keep.append(group)
                start = i + 1
    keep.append(text[start:] if depth == 0 else "")
    return "".join(keep)


def cup_as_today(text: str, sheet: FactSheet, claims: list[Claim]) -> str | None:
    """A sentence that uses the cup match as if it were today: a behaviour today's facts do not show, or a number
    that only appears in a cup comparison. Sentences that name the cup match are explicit comparisons: allowed."""
    today_text = " ".join(_without_cup(f.text) for f in sheet.facts) + " " + " ".join(_without_cup(c.text) for c in claims)
    today_numbers = set(numbers_in(today_text)) | set(numbers_in(sheet.moment.headline)) | {1.0, 2.0}
    for sentence in re.split(r"(?<=[.;!?])\s+", text):
        if "cup" in sentence.lower():
            continue
        for concept, rx in BEHAVIOUR.items():
            if rx.search(sentence):
                active = [f for f in sheet.facts if f.concept == concept and isinstance(f.value, (int, float))
                          and f.value >= ACTIVE_FROM[concept]]
                if not active:
                    return f"'{rx.search(sentence).group()}' is not what today's facts show (only the cup match)"
        cup_only = [n for n in numbers_in(sentence) if not any(round(a, 1) == round(n, 1) for a in today_numbers)]
        if cup_only:
            return f"number(s) from the cup match used for today: {', '.join(f'{n:g}' for n in cup_only)}"
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
