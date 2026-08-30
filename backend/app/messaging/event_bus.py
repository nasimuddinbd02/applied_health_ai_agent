"""Event-bus abstraction + an in-process implementation.

The design doc names Kafka / Azure Event Hubs. The contract below is
deliberately the small subset both of those and Redis Streams support
(publish, consumer group, explicit ack, dead-letter), so swapping the
implementation is a container change — nothing above this line moves.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from app.messaging.events import Event

log = logging.getLogger(__name__)

Handler = Callable[[Event], Awaitable[None]]


class EventBus(ABC):
    """Asynchronous, at-least-once event transport."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def publish(self, topic: str, event: Event) -> None: ...

    @abstractmethod
    async def consume(self, topic: str, handler: Handler, *, stop: asyncio.Event,
                      consumer_name: str) -> None:
        """Run until ``stop`` is set, invoking ``handler`` per event.

        Implementations must ack only after the handler returns, and dead-letter
        an event once it exceeds the configured delivery attempts.
        """

    @property
    def name(self) -> str:
        return type(self).__name__


class InProcessEventBus(EventBus):
    """Single-process fallback used when Redis is unavailable, and in tests.

    Same semantics as the distributed bus (queue, retry, dead-letter) so code
    written against ``EventBus`` behaves identically either way — it just does
    not survive a process restart or reach another instance.
    """

    def __init__(self, *, max_attempts: int = 3) -> None:
        self._queues: dict[str, asyncio.Queue[Event]] = {}
        self._dead_letters: list[Event] = []
        self._max_attempts = max_attempts

    def _queue(self, topic: str) -> asyncio.Queue[Event]:
        return self._queues.setdefault(topic, asyncio.Queue())

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        self._queues.clear()

    async def publish(self, topic: str, event: Event) -> None:
        await self._queue(topic).put(event)

    async def consume(self, topic: str, handler: Handler, *, stop: asyncio.Event,
                      consumer_name: str = "local") -> None:
        queue = self._queue(topic)
        while not stop.is_set():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
            except TimeoutError:
                continue
            await self._deliver(topic, event, handler, queue)

    async def _deliver(self, topic: str, event: Event, handler: Handler,
                       queue: asyncio.Queue[Event]) -> None:
        try:
            await handler(event)
        except Exception:  # noqa: BLE001
            event.attempts += 1
            if event.attempts >= self._max_attempts:
                log.exception("Dead-lettering %s after %d attempts", event.event_id, event.attempts)
                self._dead_letters.append(event)
            else:
                log.exception("Retrying %s (attempt %d)", event.event_id, event.attempts)
                await queue.put(event)

    @property
    def dead_letters(self) -> list[Event]:
        return list(self._dead_letters)
