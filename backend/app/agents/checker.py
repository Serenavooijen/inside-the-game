"""
Fact-checker, in code.

A claim passes when
1. it cites at least one fact, and every cited fact exists in the FactSheet;
2. every number in the claim matches a number in one of its cited facts
   (or in the moment headline / match state, e.g. the score or the minute).

Numbers are the part an LLM most often gets wrong, and the part a viewer can
check. Wording is left to the Narrator.

Works on a moment's FactSheet and on the Scout's TacticalFactSheet: both have
`fact(id)`, team names and a headline (the FactSheet's is on its moment).
"""

from __future__ import annotations

import re

from app.contracts import TacticalFactSheet

from .models import Claim, FactSheet, RejectedClaim

Sheet = FactSheet | TacticalFactSheet

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


def _headline(sheet: Sheet) -> str:
    return sheet.headline if isinstance(sheet, TacticalFactSheet) else sheet.moment.headline


def _allowed_numbers(sheet: Sheet, fact_ids: list[str]) -> set[float]:
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
    allowed.update(numbers_in(_headline(sheet)))
    if isinstance(sheet, TacticalFactSheet):
        allowed.update(numbers_in(sheet.minute))
        allowed.update(numbers_in(sheet.window.label))
    else:
        allowed.update(numbers_in(sheet.moment.minute))
    if sheet.match_state:
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


def check_claim(claim: Claim, sheet: Sheet) -> RejectedClaim | None:
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


def check_claims(claims: list[Claim], sheet: Sheet) -> tuple[list[Claim], list[RejectedClaim]]:
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


def unknown_names(text: str, sheet: Sheet, claims: list[Claim], allowed: frozenset[str] | set[str] = frozenset()) -> list[str]:
    """Capitalised words (players, teams, places) in the Narrator's text that appear nowhere in
    the headline, the team names or the accepted claims. `allowed`: extra lower-case words that
    are no names, e.g. the playbook's concept names for the Scout."""
    source = " ".join([_headline(sheet), *sheet.team_names.values(), *(c.text for c in claims)])
    return _names_not_in(text, {w.lower() for w in re.findall(r"[\w\-]+", source)} | set(allowed))


def _names_not_in(text: str, known: set[str]) -> list[str]:
    """Capitalised words in `text` that look like names and are not in `known` (lower case)."""
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


# ---------------------------------------------------------------- game state

_STATE_END = re.compile(r"At [^:]+: (?P<home>.+?) (?P<h>\d+)-(?P<a>\d+) (?P<away>.+?), (?P<mh>\d+) v (?P<ma>\d+)")
_STATE_TEAM = re.compile(r"At \S+ (?P<team>.+?) were (?P<state>leading|trailing|level at) \d+-\d+, (?P<m1>\d+) v (?P<m2>\d+)")
# Only unambiguous score words: "behind" and "leads to" also describe space and causes.
_CLAIMS = [("leading", re.compile(r"\b(?:leading|leads?(?! to\b)(?= \d| by| the| at\b)|in the lead|in front|ahead (?:by|at|on))\b", re.I)),
           ("trailing", re.compile(r"\b(?:trailing|trails?|chasing the game)\b", re.I)),
           ("level", re.compile(r"\b(?:tied|drawing|all square|level (?:at|on)|on level terms)\b", re.I))]
_MEN = re.compile(r"\b(?:(against|versus|vs\.?) )?(\d+) men\b", re.I)    # "against 10 men": the other team


def _worlds(sheet: Sheet) -> list[dict[str, tuple[str, int]]]:
    """Every game state the sheet's facts allow: per team name (lower case), its state and players on the pitch."""
    names = list(sheet.team_names.values())
    other = lambda n: next((x for x in names if x != n), "")
    out = []
    for f in getattr(sheet, "facts", []):
        if f.metric != "game_state":
            continue
        if m := _STATE_END.search(f.text):
            h, a = int(m["h"]), int(m["a"])
            st = ("leading", "trailing") if h > a else ("trailing", "leading") if h < a else ("level", "level")
            out.append({m["home"].lower(): (st[0], int(m["mh"])), m["away"].lower(): (st[1], int(m["ma"]))})
        elif m := _STATE_TEAM.search(f.text):
            st = {"leading": ("leading", "trailing"), "trailing": ("trailing", "leading"), "level at": ("level", "level")}[m["state"]]
            out.append({m["team"].lower(): (st[0], int(m["m1"])), other(m["team"]).lower(): (st[1], int(m["m2"]))})
    return out


def game_state_errors(text: str, sheet: Sheet) -> list[str]:
    """Claims about the score or the numbers on the pitch ("Kingsbridge lead 2-1", "Northgate, trailing",
    "with 10 men") that no game-state fact allows. The subject is the nearest team name before the words."""
    worlds = _worlds(sheet)
    if not worlds:
        return []
    names = [n.lower() for n in sheet.team_names.values()]
    errors = []
    other = lambda n: next((x for x in names if x != n), None)
    for sentence in re.split(r"(?<=[.;!?])\s+", text):
        sentence = _words_to_digits(sentence)      # "ten men" -> "10 men"; positions below refer to this text
        low = sentence.lower()

        def subject(pos: int) -> str | None:
            seen = [(low.rfind(n, 0, pos), n) for n in names]
            seen = [(i, n) for i, n in seen if i >= 0]
            return max(seen)[1] if seen else None

        for state, rx in _CLAIMS:
            for m in rx.finditer(sentence):
                team = subject(m.start())
                if team and not any(w.get(team, (None,))[0] == state for w in worlds):
                    errors.append(f"{team.title()} {state} ('{m.group()}')")
        for m in _MEN.finditer(sentence):
            team = subject(m.start())
            if team and m.group(1):
                team = other(team)
            if team and not any(w.get(team, (None, None))[1] == int(m.group(2)) for w in worlds):
                errors.append(f"{team.title()} with {m.group(2)} men")
    return errors


# ---------------------------------------------------------------- direction

# (word in the text, its opposite, only in sentences about the line or block)
_DIRECTIONS = [("more compact", "less compact", False), ("less compact", "more compact", False),
               ("more intense", "less intense", False), ("less intense", "more intense", False),
               ("higher", "deeper", True), ("deeper", "higher", True), ("lower", "higher", True)]
_LINE_CONTEXT = re.compile(r"\b(line|block)\b", re.I)


def direction_errors(text: str, facts_text: str) -> list[str]:
    """Comparatives that contradict the cited facts: the text says "less compact" where the facts only say
    "more compact". Only contradictions count; a direction the facts do not mention is left alone."""
    facts = facts_text.lower()
    errors = []
    for sentence in re.split(r"(?<=[.;!?])\s+", text):
        low = sentence.lower()
        for word, opposite, needs_line in _DIRECTIONS:
            if needs_line and not _LINE_CONTEXT.search(low):
                continue
            if re.search(rf"\b{word}\b", low) and re.search(rf"\b{opposite}\b", facts) and not re.search(rf"\b{word}\b", facts):
                errors.append(f"'{word}' where the facts say '{opposite}'")
    return list(dict.fromkeys(errors))


def check_text(text: str, sheet: Sheet, fact_ids: list[str]) -> list[float]:
    """Numbers in a free text (the Narrator's) that are not backed by these facts."""
    allowed = _allowed_numbers(sheet, fact_ids)
    return [n for n in numbers_in(text) if not _matches(n, allowed)]


# ---------------------------------------------------------------- translation

MAX_LENGTH_RATIO = 2.0      # a translation may be about twice as long as its English source, not more
_LENGTH_SLACK = 20          # characters, so a two-word source can become a three-word translation


# Number words of the target languages, 2 and up: "one" is also an article there (een, un, uno), so 1 only
# counts as a digit. English words do not count in a translation ("ten opzichte van" is no 10).
_TARGET_WORDS: dict[str, dict[str, int]] = {
    "nl": dict(zip("twee drie vier vijf zes zeven acht negen tien elf twaalf dertien veertien vijftien zestien "
                   "zeventien achttien negentien twintig dertig veertig vijftig".split(),
                   [*range(2, 21), 30, 40, 50])),
    "es": dict(zip("dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis "
                   "diecisiete dieciocho diecinueve veinte treinta cuarenta cincuenta".split(),
                   [*range(2, 21), 30, 40, 50])),
    "fr": dict(zip("deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize "
                   "dix-sept dix-huit dix-neuf vingt trente quarante cinquante".split(),
                   [*range(2, 21), 30, 40, 50])),
}
_ORDINALS = dict(zip("first second third fourth fifth sixth seventh eighth ninth tenth".split(), range(1, 11)))


def _digits(text: str) -> set[float]:
    return {round(float(m.replace(",", ".")), 2) for m in NUM.findall(text)}


def _translated_numbers(text: str, lang: str | None) -> set[float]:
    words = _TARGET_WORDS.get(lang or "", {})
    found = {float(words[w.lower()]) for w in re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", text) if w.lower() in words}
    return _digits(text) | found


_NAME_IN_TRANSLATION = re.compile(r"\b[A-Z][\w\-]*(?:[’'][\w]+)?")
_ELISION = re.compile(r"^(?:[A-Za-z]|Qu)[’']", re.I)       # L'adversaire, D'abord, Qu'il
_SENTENCE_START = ".!?¿¡:«\"“"


def _new_names(text: str, known: set[str]) -> list[str]:
    """Capitalised words in a translation that are in neither the English source nor the names of the match.
    Aware of the target languages: elisions (L'équipe), contractions (zo'n) and the Dutch genitive (Brouwers)."""
    out = []
    for m in _NAME_IN_TRANSLATION.finditer(text):
        raw = m.group()
        if _ELISION.match(raw):
            continue
        word = re.sub(r"[’'][\w]+$", "", raw)
        before = text[: m.start()].rstrip()
        # The first word of a sentence is capitalised anyway; it only looks like a name with a possessive 's
        # or a hyphen ("Zo'n" and "L'équipe" are no names).
        if (not before or before[-1] in _SENTENCE_START) and "-" not in word and not re.search(r"[’']s$", raw):
            continue
        low = word.lower()
        if low in known or low in _COMMON or (low.endswith("s") and low[:-1] in known):   # Dutch genitive: Brouwers
            continue
        if all(part in known for part in low.split("-")):
            continue
        out.append(word)
    return list(dict.fromkeys(out))


def check_translation(source: str, translated: str, names: set[str] | frozenset[str] = frozenset(),
                      lang: str | None = None) -> str | None:
    """Why this translation of a checked English text is rejected, or None when it passes.

    1. the same numbers: every number of the source is in the translation, and no new one comes in.
       0,41 and 0.41 are the same number; number words count (English in the source, the target language's
       in the translation). A 1 that the source only has as a word ("one") may go: it is an article in
       Dutch, Spanish and French. An ordinal of the source ("first half") may come back as a digit (1re).
    2. the same names: every name of `names` (players, clubs) in the source is in the translation (a
       genitive s is fine), and no capitalised word comes in that is not in the source;
    3. a sane length: at most about twice the source.
    The text is the Translator's; the code checks it, as with every other agent."""
    if not translated.strip():
        return "Empty translation"
    required = {round(n, 2) for n in numbers_in(source)}
    optional = {float(v) for w, v in _ORDINALS.items() if re.search(rf"\b{w}\b", source, re.I)}
    if 1.0 in required and 1.0 not in _digits(source):
        required.discard(1.0)
        optional.add(1.0)
    out = _translated_numbers(translated, lang)
    lost, new = required - out, out - required - optional
    if lost or new:
        show = lambda xs: ", ".join(f"{n:g}" for n in sorted(xs))  # noqa: E731
        parts = ([f"new number(s) {show(new)}"] if new else []) + ([f"missing {show(lost)}"] if lost else [])
        return f"Numbers differ from the English source: {'; '.join(parts)}"
    missing = [n for n in sorted(names, key=len, reverse=True)
               if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", source)
               and not re.search(rf"(?<![\w-]){re.escape(n)}(?:[’']?s)?(?![\w-])", translated)]
    if missing:
        return f"Name(s) missing from the translation: {', '.join(missing)}"
    # Only the source: a player of the squad who is not in the checked English text is a new name too.
    extra = _new_names(translated, {w.lower() for w in re.findall(r"[\w\-]+", source)})
    if extra:
        return f"Name(s) not in the English source: {', '.join(extra)}"
    if len(translated) > MAX_LENGTH_RATIO * len(source) + _LENGTH_SLACK:
        return f"Translation too long: {len(translated)} characters for {len(source)}"
    return None
