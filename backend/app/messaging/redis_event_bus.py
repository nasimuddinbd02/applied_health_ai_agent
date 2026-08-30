"""Redis Streams event bus — the Kafka/Event-Hubs stand-in for this deployment.

Why Streams and not plain Pub/Sub: agent work must not be lost when no worker
happens to be listening. A Stream is a durable, replayable log with consumer
groups, per-message acknowledgement and pending-entry recovery — the same
guarantees the design doc leans on Kafka for.

  events:chat.user_message        the work log
  events:chat.user_message:dlq    dead letters (poison messages)

Cross-server *notification* (delivering an agent reply to the pod that owns a
customer's socket) is a different problem and uses Pub/Sub — see
``app.realtime.dispatcher``.
"""

import asyncio
import logging

from app.core.config import Settings
from app.messaging.event_bus import EventBus, Handler
from app.messaging.events import Event
from app.messaging.redis_client import RedisClient

log = logging.getLogger(__name__)


class RedisStreamEventBus(EventBus):
    def __init__(self, redis: RedisClient, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings
        self._groups_ready: set[str] = set()

    # ----------------------------------------------------------------- #
    # Lifecycle
    # ----------------------------------------------------------------- #
    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def _stream(self, topic: str) -> str:
        return self._settings.stream(topic)

    def _dlq(self, topic: str) -> str:
        return f"{self._stream(topic)}:dlq"

    async def _ensure_group(self, topic: str) -> None:
        """Create the consumer group (idempotently) before first read."""
        if topic in self._groups_ready:
            return
        client = self._redis.client()
        try:
            await client.xgroup_create(
                self._stream(topic), self._settings.event_consumer_group,
                id="0", mkstream=True,
            )
        except Exception as err:  # noqa: BLE001 — BUSYGROUP just means it exists
            if "BUSYGROUP" not in str(err):
                raise
        self._groups_ready.add(topic)

    # ----------------------------------------------------------------- #
    # Produce
    # ----------------------------------------------------------------- #
    async def publish(self, topic: str, event: Event) -> None:
        await self._redis.client().xadd(self._stream(topic), {"data": event.to_json()})

    # ----------------------------------------------------------------- #
    # Consume
    # ----------------------------------------------------------------- #
    async def consume(self, topic: str, handler: Handler, *, stop: asyncio.Event,
                      consumer_name: str = "worker") -> None:
        await self._ensure_group(topic)
        client = self._redis.client()
        stream, group = self._stream(topic), self._settings.event_consumer_group

        while not stop.is_set():
            try:
                await self._reclaim_stalled(client, stream, group, consumer_name, handler, topic)
                batches = await client.xreadgroup(
                    group, consumer_name, {stream: ">"}, count=10, block=1000,
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — a Redis blip must not kill the worker
                log.exception("Stream read failed on %s; retrying", stream)
                await asyncio.sleep(1.0)
                continue

            for _stream_key, entries in batches or []:
                for entry_id, fields in entries:
                    await self._handle_entry(
                        client, stream, group, topic, entry_id, fields, handler
                    )

    async def _reclaim_stalled(self, client, stream: str, group: str, consumer_name: str,
                               handler: Handler, topic: str) -> None:
        """Take over entries a crashed worker read but never acked.

        This is the "agent worker crashes → durable state enables retry" row of
        the design doc's failure table.
        """
        try:
            reclaimed = await client.xautoclaim(
                stream, group, consumer_name,
                min_idle_time=self._settings.event_claim_idle_ms, count=10,
            )
        except Exception:  # noqa: BLE001 — older Redis without XAUTOCLAIM
            return
        entries = reclaimed[1] if len(reclaimed) > 1 else []
        for entry_id, fields in entries or []:
            await self._handle_entry(client, stream, group, topic, entry_id, fields, handler)

    async def _handle_entry(self, client, stream: str, group: str, topic: str,
                            entry_id: str, fields: dict, handler: Handler) -> None:
        raw = (fields or {}).get("data")
        if not raw:
            await client.xack(stream, group, entry_id)
            return
        try:
            event = Event.from_json(raw)
        except Exception:  # noqa: BLE001 — unparseable: straight to the DLQ
            log.exception("Undecodable event on %s; dead-lettering", stream)
            await client.xadd(self._dlq(topic), {"data": raw})
            await client.xack(stream, group, entry_id)
            return

        try:
            await handler(event)
        except Exception:  # noqa: BLE001
            event.attempts += 1
            if event.attempts >= self._settings.event_max_delivery_attempts:
                log.exception("Dead-lettering %s after %d attempts", event.event_id, event.attempts)
                await client.xadd(self._dlq(topic), {"data": event.to_json()})
            else:
                log.exception("Retrying %s (attempt %d)", event.event_id, event.attempts)
                await client.xadd(stream, {"data": event.to_json()})
        finally:
            # Ack unconditionally: the entry has either been handled, requeued
            # as a fresh entry, or dead-lettered. Leaving it pending would make
            # XAUTOCLAIM redeliver it on top of the retry we just queued.
            await client.xack(stream, group, entry_id)
