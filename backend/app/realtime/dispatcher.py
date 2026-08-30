"""Routes a server -> client event to the instance that owns the socket.

This is the piece the design doc's §6 and step 7 of the "final mental model"
describe: an agent worker finishes somewhere in the cluster and needs to reach
a customer whose WebSocket lives in a *different* process.

    worker  ──dispatch(conversation_id, event)──►  SessionRegistry (who owns it?)
                                                     │
                              owner is me ───────────┼──────────► ConnectionManager
                                                     │
                              owner is elsewhere ────┴──► Redis PUB ws:node:{id}
                                                              │
                                             that instance's SUB loop ──► its
                                                              ConnectionManager

Pub/Sub (not Streams) is right here: this is a *notification* to whoever is
holding a live socket right now. If nobody is connected the event is correctly
dropped — the durable conversation record is what a reconnecting client
replays from.
"""

import asyncio
import json
import logging

from app.core.config import Settings
from app.messaging.redis_client import RedisClient
from app.realtime.connection_manager import ConnectionManager
from app.realtime.session_registry import SessionRegistry

log = logging.getLogger(__name__)


class RealtimeDispatcher:
    def __init__(self, redis: RedisClient, registry: SessionRegistry,
                 connections: ConnectionManager, settings: Settings) -> None:
        self._redis = redis
        self._registry = registry
        self._connections = connections
        self._settings = settings
        self._server_id = settings.instance_id
        self._task: asyncio.Task | None = None
        self._pubsub = None

    @property
    def server_id(self) -> str:
        return self._server_id

    def _channel(self, server_id: str) -> str:
        return self._settings.key("ws", "node", server_id)

    # ----------------------------------------------------------------- #
    # Outbound
    # ----------------------------------------------------------------- #
    async def dispatch(self, conversation_id: str, event: dict) -> int:
        """Deliver ``event`` to every live socket for the conversation.

        Returns the number of sockets this process wrote to directly; remote
        instances deliver their own and are not counted here.
        """
        delivered = await self._connections.send_to_conversation(conversation_id, event)

        if not self._redis.available:
            return delivered

        owners = await self._registry.servers_for_conversation(conversation_id)
        remote = owners - {self._server_id}
        if not remote:
            return delivered

        envelope = json.dumps({"conversation_id": conversation_id, "event": event}, default=str)
        for server_id in remote:
            try:
                await self._redis.client().publish(self._channel(server_id), envelope)
            except Exception:  # noqa: BLE001 — a lost notification is recoverable
                log.exception("Cross-server publish to %s failed", server_id)
        return delivered

    # ----------------------------------------------------------------- #
    # Inbound
    # ----------------------------------------------------------------- #
    async def start(self) -> None:
        """Subscribe to this instance's channel and pump events to local sockets."""
        if not self._redis.available or self._task is not None:
            return
        try:
            self._pubsub = self._redis.client().pubsub(ignore_subscribe_messages=True)
            await self._pubsub.subscribe(self._channel(self._server_id))
        except Exception:  # noqa: BLE001
            log.exception("Could not subscribe to %s", self._channel(self._server_id))
            self._pubsub = None
            return
        self._task = asyncio.create_task(self._listen(), name="realtime-dispatcher")
        log.info("Realtime dispatcher listening on %s", self._channel(self._server_id))

    async def _listen(self) -> None:
        assert self._pubsub is not None
        while True:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — reconnect rather than die
                log.exception("Pub/Sub read failed; retrying")
                await asyncio.sleep(1.0)
                continue
            if not message:
                continue
            try:
                envelope = json.loads(message["data"])
                await self._connections.send_to_conversation(
                    envelope["conversation_id"], envelope["event"]
                )
            except Exception:  # noqa: BLE001
                log.exception("Dropping malformed cross-server envelope")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()
            except Exception:  # noqa: BLE001
                pass
            self._pubsub = None
