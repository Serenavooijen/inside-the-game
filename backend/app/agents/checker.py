"""
Fact-checker, in code.

A claim passes when
1. it cites at least one fact, and every cited fact exists in the FactSheet;
2. every number in the claim matches a number in one of its cited facts
   (or in the moment headline / match state, e.g. the score or the minute).

Numbers are the part an LLM most often gets wrong, and the part a viewer can
check. Wording is left to the Narrator.
"""

from __future__ import annotations

import re

from .models import Claim, FactSheet, RejectedClaim

NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?")

_UNITS = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
WORD_NUM = re.compile(r"\b(" + "|".join(list(_TENS) + _UNITS[::-1]) + r")(?:-(" + "|".join(_UNITS[1:10]) + r"))?\b", re.I)


def _words_to_digits(text: str) -> str:
    """'eleven metres' -> '11 metres', 'twenty-five' -> '25', so the Narrator cannot slip a number past the check."""

    def repl(m: re.Match) -> str:
        a, b = m.group(1).lower(), (m.group(2) or "").lower()
        n = _TENS.get(a, _UNITS.index(a) if a in _UNITS else 0) + (_UNITS.index(b) if b else 0)
        return str(n)

    return WORD_NUM.sub(repl, text)


def numbers_in(text: str) -> list[float]:
    out = []
    text = _words_to_digits(text)
    for m in NUM.findall(text):
        try:
            out.append(float(m.replace(",", ".")))
        except ValueError:
            pass
    return out


def _allowed_numbers(sheet: FactSheet, fact_ids: list[str]) -> set[float]:
    allowed: set[float] = set()
    for fid in fact_ids:
        f = sheet.fact(fid)
        if not f:
            continue
        allowed.update(numbers_in(f.text))
        if isinstance(f.value, (int, float)):
            allowed.add(float(f.value))
            allowed.add(round(float(f.value), 1))
            allowed.add(round(float(f.value)))
        else:
            allowed.update(numbers_in(str(f.value)))
        if f.window:
            allowed.update(numbers_in(f.window))
    # context the claim may always use
    allowed.update(numbers_in(sheet.moment.headline))
    allowed.update(numbers_in(sheet.moment.minute))
    allowed.update(float(x) for x in sheet.match_state.score)
    allowed.update(float(x) for x in sheet.match_state.players_on_pitch)
    # small counting words that are rarely factual claims
    allowed.update({1.0, 2.0})
    return allowed


def _decimals(n: float) -> int:
    s = f"{n:g}"
    return len(s.split(".")[1]) if "." in s else 0


def _matches(n: float, allowed: set[float]) -> bool:
    """n matches when an allowed value, rounded to n's precision, equals n (so 0.41 ~ 0.412, 57 ~ 57.2)."""
    d = _decimals(n)
    return any(round(a, d) == round(n, d) for a in allowed)


def check_claim(claim: Claim, sheet: FactSheet) -> RejectedClaim | None:
    if not claim.fact_ids:
        return RejectedClaim(text=claim.text, reason="No supporting fact cited", fact_ids=[])
    missing = [fid for fid in claim.fact_ids if sheet.fact(fid) is None]
    if missing:
        return RejectedClaim(text=claim.text, reason=f"Unknown fact id(s): {', '.join(missing)}", fact_ids=claim.fact_ids)
    allowed = _allowed_numbers(sheet, claim.fact_ids)
    wrong = [n for n in numbers_in(claim.text) if not _matches(n, allowed)]
    if wrong:
        shown = ", ".join(f"{n:g}" for n in wrong)
        return RejectedClaim(text=claim.text, reason=f"Number(s) not in the cited facts: {shown}", fact_ids=claim.fact_ids)
    return None


def check_claims(claims: list[Claim], sheet: FactSheet) -> tuple[list[Claim], list[RejectedClaim]]:
    ok, rejected = [], []
    for c in claims:
        r = check_claim(c, sheet)
        (rejected if r else ok).append(r or c)
    return ok, rejected


NAME = re.compile(r"\b[A-Z][\w\-]*(?:[’'][A-Za-z]+)?")
_COMMON = set("""a an the it its this that these those there their they he his him she her we our you
and but so yet or if as at by in on of to for from with without after before since until while when
then now still just only even also both either neither each every all no not one two three despite
although though because however meanwhile what who why how where which half time full first second
goal goals xg xgot var tv""".split())


def unknown_names(text: str, sheet: FactSheet, claims: list[Claim]) -> list[str]:
    """Capitalised words (players, teams, places) in the Narrator's text that appear nowhere in
    the headline, the team names or the accepted claims."""
    source = " ".join([sheet.moment.headline, *sheet.team_names.values(), *(c.text for c in claims)])
    known = {w.lower() for w in re.findall(r"[\w\-]+", source)}
    out = []
    for m in NAME.finditer(text):
        raw = m.group()
        word = re.sub(r"[’'][A-Za-z]+$", "", raw)
        # The first word of a sentence is capitalised anyway ("Following the red card ...").
        # Only treat it as a name when it looks like one: a possessive or a double-barrelled name.
        before = text[: m.start()].rstrip()
        sentence_start = not before or before[-1] in ".!?"
        if sentence_start and raw == word and "-" not in word:
            continue
        if word.lower() in known or word.lower() in _COMMON:
            continue
        if all(part.lower() in known for part in word.split("-")):
            continue
        out.append(word)
    return list(dict.fromkeys(out))


def check_text(text: str, sheet: FactSheet, fact_ids: list[str]) -> list[float]:
    """Numbers in a free text (the Narrator's) that are not backed by these facts."""
    allowed = _allowed_numbers(sheet, fact_ids)
    return [n for n in numbers_in(text) if not _matches(n, allowed)]
