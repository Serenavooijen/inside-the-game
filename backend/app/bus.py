"""EventBus: brings messages from the simulator to every listener (SSE connections).

Each subscriber gets its own bounded queue. When a queue is full the oldest message
is dropped: the simulator never waits for a slow browser. A reconnecting browser
calls GET /state, so a dropped message is never lost for good.
"""
import asyncio
from typing import Any

Message = tuple[str, dict[str, Any]]   # (SSE event name, JSON payload)


class EventBus:
    def __init__(self, maxsize: int = 256) -> None:
        self.maxsize = maxsize
        self._subscribers: set[asyncio.Queue[Message]] = set()

    def subscribe(self) -> asyncio.Queue[Message]:
        q: asyncio.Queue[Message] = asyncio.Queue(self.maxsize)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Message]) -> None:
        self._subscribers.discard(q)

    def publish(self, name: str, data: dict[str, Any]) -> None:
        """Never blocks."""
        for q in self._subscribers:
            if q.full():
                q.get_nowait()
            q.put_nowait((name, data))

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
