"""
The Translator: a checked English text in other languages, checked again by the code.

    await translate(item, names, model=..., cache=...) -> {"nl": Translation, "es": ..., "fr": ...}

The agents write and check in English, as before: the fact-check is built on English (number words,
comparatives, the game state). Only a card that is done and checked (or corrected) is translated, and
every translation is compared with its English source by `check_translation`: the same numbers, the
same names, a sane length. A translation that fails, or comes too late, is "rejected" and the UI keeps
the English text. Evidence lines (the facts) stay English.

Translations are cached per text and per language, so the same text is never translated twice, also
not after a seek. Timeouts and model errors are not cached: the next time it is tried again.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from app.contracts import Commentary, Insight, TranslatedObservation, Translation

from .checker import check_translation
from .deadline import within
from .llm import ModelClient
from .prompts import translator_prompt

log = logging.getLogger(__name__)

TRANSLATE_DEADLINE_S = float(os.getenv("TRANSLATE_DEADLINE_S", "6"))
CHUNK = 3                   # texts per Translator call; the chunks of a card run in parallel
DEFAULT_LANGUAGES = "nl,es,fr"
RTL = {"ar", "he", "fa", "ur"}      # right-to-left: needs layout work first


def languages() -> list[str]:
    """ITG_LANGUAGES=nl,es,fr (the default); empty turns translation off. English is the source, always there."""
    raw = os.getenv("ITG_LANGUAGES", DEFAULT_LANGUAGES)
    out = [code.strip().lower() for code in raw.split(",") if code.strip()]
    return [c for c in dict.fromkeys(out) if c != "en" and c not in RTL]


Item = Insight | Commentary


def translatable(item: Item) -> bool:
    """Only checked English: a finished card with status checked or corrected (never a fallback)."""
    if isinstance(item, Commentary):
        return bool(item.text)
    return item.phase == "done" and item.status in ("checked", "corrected") and bool(segments(item))


def segments(item: Item) -> list[str]:
    """The English texts of a card that the UI shows, in a fixed order."""
    if isinstance(item, Commentary):
        return [item.text]
    if item.observations:       # tactics, the scouting report and a substitution's impact card
        return [t for o in item.observations for t in (o.observation, o.consequence, o.coach_action) if t]
    if item.type == "substitution":
        return list(item.substitution.watch) if item.substitution else []
    return [item.text] if item.text else []


def _fields(item: Item, out: dict[str, str]) -> dict:
    """The translated fields of the Translation, from the translations per segment."""
    if isinstance(item, Commentary):
        return {"text": out[item.text]}
    if item.observations:
        return {"observations": [TranslatedObservation(
            observation=out[o.observation], consequence=out[o.consequence] if o.consequence else "",
            coach_action=out[o.coach_action] if o.coach_action else None) for o in item.observations]}
    if item.type == "substitution":
        return {"watch": [out[w] for w in item.substitution.watch]}
    return {"text": out[item.text]}


class TranslationCache:
    """(language, English text) -> (translation, reason it was rejected or None). In memory, per process."""

    def __init__(self) -> None:
        self._d: dict[tuple[str, str], tuple[str, str | None]] = {}

    def get(self, lang: str, text: str) -> tuple[str, str | None] | None:
        return self._d.get((lang, text))

    def put(self, lang: str, text: str, translated: str, reason: str | None) -> None:
        self._d[(lang, text)] = (translated, reason)

    def __len__(self) -> int:
        return len(self._d)


def from_cache(item: Item, langs: list[str], cache: TranslationCache) -> dict[str, Translation] | None:
    """The translations of `item` when every text is already in the cache for every language, else None."""
    texts = segments(item)
    out = {}
    for lang in langs:
        hits = [cache.get(lang, t) for t in texts]
        if not texts or any(h is None for h in hits):
            return None
        out[lang] = _result(item, lang, texts, hits, 0, None)
    return out


def _result(item: Item, lang: str, texts: list[str], hits: list[tuple[str, str | None]], latency_ms: int,
            tokens: int | None) -> Translation:
    reason = next((r for _, r in hits if r), None)
    if reason:
        return Translation(status="rejected", reason=reason, latency_ms=latency_ms, tokens=tokens)
    return Translation(status="checked", latency_ms=latency_ms, tokens=tokens,
                       **_fields(item, {t: h[0] for t, h in zip(texts, hits)}))


async def translate_one(item: Item, lang: str, names: set[str], *, model: ModelClient, cache: TranslationCache,
                        deadline_s: float | None = None) -> Translation:
    """One language: the texts not in the cache go to the Translator (in chunks of CHUNK, in parallel, each with
    the deadline), then every text is checked against its source."""
    texts = segments(item)
    todo = list(dict.fromkeys(t for t in texts if cache.get(lang, t) is None))
    start = time.perf_counter()
    ms = lambda: round((time.perf_counter() - start) * 1000)  # noqa: E731
    deadline = deadline_s or TRANSLATE_DEADLINE_S
    tokens: int | None = None
    if todo:
        if not hasattr(model, "translate"):
            return Translation(status="rejected", reason=f"No Translator in the {model.name} set-up")
        chunks = [todo[k:k + CHUNK] for k in range(0, len(todo), CHUNK)]
        results = await asyncio.gather(*(within(model.translate(lang, c, translator_prompt(lang, c)), deadline)
                                         for c in chunks), return_exceptions=True)
        failure = None
        for chunk, r in zip(chunks, results):
            if isinstance(r, asyncio.CancelledError):
                raise r
            if isinstance(r, BaseException):
                failure = failure or (f"Translation timed out after {deadline:g} s" if isinstance(r, TimeoutError)
                                      else f"Translator error: {type(r).__name__}")   # the English text stays
                continue
            draft, used = r
            tokens = (tokens or 0) + used if used else tokens
            if len(draft.texts) != len(chunk):
                failure = failure or f"{len(draft.texts)} translation(s) for {len(chunk)} text(s)"
                continue
            for source, translated in zip(chunk, draft.texts):       # what came back is checked and cached
                translated = " ".join(translated.split())
                reason = check_translation(source, translated, names, lang)
                if reason:
                    log.warning("Translation rejected (%s): %s\n  EN: %s\n  %s: %s", lang, reason, source, lang.upper(), translated)
                cache.put(lang, source, translated, reason)
        if failure:
            return Translation(status="rejected", reason=failure, latency_ms=ms(), tokens=tokens)
    return _result(item, lang, texts, [cache.get(lang, t) for t in texts], ms(), tokens)


async def translate(item: Item, names: set[str], *, model: ModelClient, cache: TranslationCache,
                    langs: list[str] | None = None, deadline_s: float | None = None) -> dict[str, Translation]:
    """Every language at once; each has its own deadline, apart from the deadlines of the other agents."""
    langs = languages() if langs is None else langs
    done = await asyncio.gather(*(translate_one(item, lang, names, model=model, cache=cache, deadline_s=deadline_s)
                                  for lang in langs))
    return dict(zip(langs, done))


__all__ = ["TranslationCache", "from_cache", "languages", "segments", "translatable", "translate", "translate_one"]
