"""A deadline that is a deadline.

asyncio.wait_for cancels the work at the deadline and then *waits until the cancellation is done*. A model
call stuck in its HTTP client can take minutes to unwind (seen once: 727 s for a 15 s deadline). `within`
returns at the deadline, no matter what: the work is cancelled and left to finish unwinding on its own.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from typing import TypeVar

log = logging.getLogger(__name__)
T = TypeVar("T")


async def within(work: Awaitable[T], seconds: float) -> T:
    """The result of `work`, or TimeoutError after `seconds` (without waiting for the cancellation)."""
    task = asyncio.ensure_future(work)
    try:
        done, _ = await asyncio.wait({task}, timeout=seconds)
    except asyncio.CancelledError:
        task.cancel()
        raise
    if task in done:
        return task.result()
    task.cancel()
    task.add_done_callback(_quiet)
    raise TimeoutError(f"no result within {seconds:g} s")


def _quiet(task: asyncio.Task) -> None:
    """Retrieve the outcome of an abandoned task, so asyncio does not log 'exception was never retrieved'."""
    if not task.cancelled() and task.exception() is not None:
        log.info("Abandoned model call ended with %r", task.exception())
