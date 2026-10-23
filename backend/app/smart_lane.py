"""Smart lane: runs the agent workflow for each moment without ever holding up the match.

Per docs/overdracht-agents.md: every moment is its own task, at most two run at once,
the workflow has its own 6 s deadline and this module adds an 8 s safety net. On a
seek or load the simulator cancels everything, because those results belong to an
old generation.
"""
import asyncio
import logging
from collections.abc import Callable

from app.agents import run_workflow
from app.agents.llm import ModelClient
from app.agents.workflow import INSIGHT_TYPE, template_text
from app.contracts import FactSheet, Insight, Moment

log = logging.getLogger(__name__)

CONCURRENCY = 2
SAFETY_NET_S = 8.0

Publish = Callable[[Insight], None]


class SmartLane:
    def __init__(self, model: ModelClient, concurrency: int = CONCURRENCY, safety_net_s: float = SAFETY_NET_S) -> None:
        self.model = model
        self.safety_net_s = safety_net_s
        self._slots = asyncio.Semaphore(concurrency)
        self._tasks: set[asyncio.Task] = set()

    async def warmup(self) -> None:
        """Fetch a token and open the connection once (4-9 s for Foundry), so the first goal is not late."""
        warm = getattr(self.model, "warmup", None)
        if warm is None:
            return
        try:
            await warm()
        except Exception:  # no Azure login locally: the workflow falls back to template text
            log.warning("Agent model warm-up failed; insights will use the fallback text", exc_info=True)

    def submit(self, moment: Moment, sheet: FactSheet, generation: int, publish: Publish) -> None:
        task = asyncio.get_running_loop().create_task(self._run(moment, sheet, generation, publish))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def cancel_all(self) -> None:
        for task in list(self._tasks):
            task.cancel()

    async def wait(self) -> None:
        """Until every running moment is done (for tests and shutdown)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _run(self, moment: Moment, sheet: FactSheet, generation: int, publish: Publish) -> None:
        async with self._slots:
            try:
                await asyncio.wait_for(
                    run_workflow(moment, sheet, publish, generation=generation, model=self.model),
                    timeout=self.safety_net_s,
                )
            except TimeoutError:
                publish(_safety_fallback(moment, sheet, generation, self.safety_net_s))


def _safety_fallback(moment: Moment, sheet: FactSheet, generation: int, after_s: float) -> Insight:
    first = sheet.facts[:1]
    return Insight(
        id=f"i-{moment.moment_id}", t=moment.t, minute=moment.minute, moment_id=moment.moment_id,
        type=INSIGHT_TYPE[moment.kind], team=moment.team,
        card="red" if moment.kind == "red_card" else "yellow" if moment.kind == "yellow_card" else None,
        text=template_text(sheet), status="fallback", phase="done",
        fallback_reason=f"Workflow did not finish within {after_s:g} s",
        evidence=[f.text for f in first], cited_fact_ids=[f.fact_id for f in first], generation=generation,
    )
