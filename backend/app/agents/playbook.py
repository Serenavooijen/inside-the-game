"""The tactics playbook (knowledge/tactics_playbook.md) as data, for the Scout.

- `one_liner(id)`: the concept condensed to one line (name, consequence, coach response).
  The Scout only gets the lines of the concepts whose detector fired, never the whole file.
- `CONCEPT_TERMS`: words from the concept names, allowed in the Scout's text even when
  capitalised, so unknown_names does not mistake "Lavolpiana" or "PPDA" for an invented name.
- `template_observations(sheet)`: observations straight from the facts and the playbook,
  without a model: the offline Scout and the fallback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.contracts import CompareToCup, Fact, TacticalFactSheet, TacticalObservation

PLAYBOOK = Path(__file__).parent / "knowledge" / "tactics_playbook.md"
_TITLE = re.compile(r"^\*\*([A-Z]\d) · (.+?)\*\*\s*$")
_FIELD = re.compile(r"^- \*\*(Looks like|Signals|Consequence|Coach response):\*\* (.+)$")


@dataclass(frozen=True)
class Concept:
    id: str
    name: str
    consequence: str = ""
    coach: str = ""


@lru_cache(maxsize=1)
def concepts() -> dict[str, Concept]:
    out: dict[str, Concept] = {}
    current: dict | None = None
    for line in PLAYBOOK.read_text(encoding="utf-8").splitlines():
        if m := _TITLE.match(line.strip()):
            current = {"id": m.group(1), "name": m.group(2)}
            out[current["id"]] = Concept(**current)
        elif current and (m := _FIELD.match(line.strip())):
            key = {"Consequence": "consequence", "Coach response": "coach"}.get(m.group(1))
            if key:
                current[key] = m.group(2).strip()
                out[current["id"]] = Concept(**current)
    return out


def one_liner(concept_id: str) -> str:
    c = concepts().get(concept_id)
    if not c:
        return ""
    parts = [f"{c.id} {c.name}"]
    if c.consequence:
        parts.append(f"consequence: {c.consequence}")
    if c.coach:
        parts.append(f"coach: {c.coach}")
    return " · ".join(parts)


@lru_cache(maxsize=1)
def concept_terms() -> frozenset[str]:
    words = set()
    for c in concepts().values():
        words.update(w.lower() for w in re.findall(r"[A-Za-z][\w\-]*", c.name))
    # tactical vocabulary that is often capitalised
    words.update({"ppda", "xg", "gegenpressing", "salida", "lavolpiana", "like-for-like", "6", "8", "10",
                  # hyphenated terms look like double-barrelled names at the start of a sentence
                  "far-side", "full-back", "full-backs", "centre-back", "centre-backs", "wing-back", "wing-backs",
                  "half-space", "half-spaces", "counter-press", "counter-pressing", "counter-attack",
                  "counter-attacks", "one-two", "one-on-one", "man-marking", "man-oriented", "set-piece",
                  "set-pieces", "box-to-box", "low-block", "high-block", "mid-block", "third-man", "re-press"})
    return frozenset(words)


def _plain_sentence(text: str, like: str = "") -> str:
    """The sentence without numbers (digits or words: a template may never add one) that shares the
    most words with `like`, e.g. the "high block" sentence for a fact about a high block."""
    from .checker import numbers_in

    words = {w for w in re.findall(r"[a-z]{4,}", like.lower())}
    best, score = "", -1
    for s in re.split(r"(?<=[.!?])\s+", text):
        if not s or numbers_in(s):
            continue
        n = len(words & set(re.findall(r"[a-z]{4,}", s.lower())))
        if n > score:
            best, score = s.strip(), n
    return best


# Share-based concepts: below this value the concept is not what the team does now (only its absence is),
# so the playbook's consequence would describe the wrong thing. Templates skip such facts.
ACTIVE_FROM = {"B1": 30, "B2": 30, "B3": 30, "B5": 20, "T1": 35}
# In-between values have no consequence in the playbook (it describes high and low blocks, intense presses).
IN_BETWEEN = re.compile(r"\b(mid block|was medium|moderate pressing)\b")
_CUP_PCT = re.compile(r"cup match: (\d+(?:\.\d+)?)%")


def below_threshold(f: Fact) -> bool:
    return isinstance(f.value, (int, float)) and f.value < ACTIVE_FROM.get(f.concept or "", -1)


def visible_to_scout(f: Fact) -> bool:
    """A share below its concept's threshold says the team did not do it: hide it, unless the cup baseline was
    above the threshold. Then the absence is exactly the change the staff wants ("0% today, cup match: 58%")."""
    if not below_threshold(f):
        return True
    m = _CUP_PCT.search(f.text)
    return bool(m and float(m.group(1)) >= ACTIVE_FROM[f.concept])


ABSENT_CONSEQUENCE = "A clear change from the cup plan: the scouted pattern is not there today."
ABSENT_COACH = "Check whether the plan for this phase still fits what the opponent does today."


def compare_from_text(fact: Fact) -> CompareToCup:
    """What the fact itself says about the cup match: 'changed', 'same' or 'n/a'."""
    text = fact.text
    if "cup match" not in text.lower():
        return "n/a"
    if re.search(r"\b(higher|deeper|more compact|less compact|more intense|less intense) than the cup match", text):
        return "changed"
    cup = text[text.lower().index("cup match"):]
    if re.search(r"\b(up|down) \d", cup):
        return "changed"
    if fact.concept == "B6" and isinstance(fact.value, str):
        m = re.search(r"cup match: ([\d-]+)", cup)
        return "same" if m and m.group(1) == fact.value else "changed"
    return "same"


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def template_observations(sheet: TacticalFactSheet, n: int = 3) -> list[TacticalObservation]:
    """Observations from the first facts (one concept and team each) plus the playbook's words."""
    out, seen = [], set()
    for f in sheet.facts:
        key = (f.concept, f.team)
        if key in seen:
            continue
        if not visible_to_scout(f) or IN_BETWEEN.search(f.text) or f.concept == "G3" and f.metric == "game_state":
            continue
        seen.add(key)
        c = concepts().get(f.concept or "")
        if below_threshold(f):              # visible only because the cup baseline was above the threshold
            consequence, coach = ABSENT_CONSEQUENCE, ABSENT_COACH
        else:
            consequence = _cap(_plain_sentence(c.consequence, f.text)) if c else ""
            coach = _cap(_plain_sentence(c.coach, f.text)) if c else ""
        if not consequence:
            continue
        out.append(TacticalObservation(
            observation=f.text.rstrip(".") + ".", fact_ids=[f.fact_id], consequence=consequence,
            coach_action=coach or None, compare_to_cup=compare_from_text(f), team=f.team,
        ))
        if len(out) == n:
            break
    return out
