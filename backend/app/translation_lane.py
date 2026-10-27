"""Translation lane: translates every finished, checked card after the fact, without holding up the match.

A card goes out in English exactly as before (analysing -> streaming -> done). Only then does the lane
start: the Translator per language, the translation check, and one more update of the same card (same id)
with `translations`. The other lanes and their deadlines do not change. On a seek or load the simulator
cancels the running translations: they belong to an old generation. The cache survives, so a text that
comes back after a seek is not translated again.
"""
import asyncio
import logging
from collections.abc import Callable

from app.agents.llm import ModelClient
from app.agents.translator import TranslationCache, from_cache, languages, translatable, translate
from app.contracts import Commentary, Insight, Translation

log = logging.getLogger(__name__)

CONCURRENCY = 3

Publish = Callable[[dict[str, Translation]], None]


class TranslationLane:
    def __init__(self, model: ModelClient, langs: list[str] | None = None, concurrency: int = CONCURRENCY,
                 deadline_s: float | None = None) -> None:
        self.model = model
        self.langs = languages() if langs is None else langs
        self.deadline_s = deadline_s
        self.cache = TranslationCache()
        self.names: set[str] = set()     # players and clubs of the match: they stay as they are
        self._slots = asyncio.Semaphore(concurrency)
        self._tasks: set[asyncio.Task] = set()

    def set_names(self, names: set[str]) -> None:
        self.names = {n for n in names if n}

    def cached(self, item: Insight | Commentary) -> dict[str, Translation] | None:
        """The translations straight from the cache, or None when something still has to be translated."""
        return from_cache(item, self.langs, self.cache) if self.langs and translatable(item) else None

    def submit(self, item: Insight | Commentary, publish: Publish) -> None:
        """Translate `item` in the background and call publish(translations) when done."""
        if not self.langs or not translatable(item):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:        # a seek runs in FastAPI's thread pool: the card stays English until a reload
            return
        task = loop.create_task(self._run(item, publish))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def cancel_all(self) -> None:
        for task in list(self._tasks):
            task.cancel()

    async def wait(self) -> None:
        """Until every running translation is done (for tests and shutdown)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _run(self, item: Insight | Commentary, publish: Publish) -> None:
        async with self._slots:
            try:
                result = await translate(item, self.names, model=self.model, cache=self.cache, langs=self.langs,
                                         deadline_s=self.deadline_s)
            except asyncio.CancelledError:
                raise
            except Exception:  # never break the match: the card stays English
                log.warning("Translation of %s failed", getattr(item, "id", item.t), exc_info=True)
                return
            publish(result)
