"""Per-process registry of live WebSocket objects (design doc §21).

This map is **local to one server instance** — a WebSocket cannot be moved or
serialised, so the socket for a customer only ever exists in the process that
accepted it. Redis holds the *metadata* saying which process that is; see
``app.realtime.session_registry``.
"""

import asyncio
import logging
from dataclasses import dataclass

from starlette.websockets import WebSocket, WebSocketState

log = logging.getLogger(__name__)


@dataclass
class Connection:
    connection_id: str
    conversation_id: str
    session_id: str
    websocket: WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, Connection] = {}
        self._by_conversation: dict[str, set[str]] = {}
        self._by_session: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    # ----------------------------------------------------------------- #
    # Membership
    # ----------------------------------------------------------------- #
    async def add(self, connection: Connection) -> None:
        async with self._lock:
            self._connections[connection.connection_id] = connection
            self._by_conversation.setdefault(connection.conversation_id, set()).add(
                connection.connection_id
            )
            self._by_session.setdefault(connection.session_id, set()).add(
                connection.connection_id
            )

    async def remove(self, connection_id: str) -> Connection | None:
        async with self._lock:
            connection = self._connections.pop(connection_id, None)
            if connection is None:
                return None
            for index, key in (
                (self._by_conversation, connection.conversation_id),
                (self._by_session, connection.session_id),
            ):
                ids = index.get(key)
                if ids is not None:
                    ids.discard(connection_id)
                    if not ids:
                        index.pop(key, None)
            return connection

    def get(self, connection_id: str) -> Connection | None:
        return self._connections.get(connection_id)

    def session_connection_count(self, session_id: str) -> int:
        return len(self._by_session.get(session_id, ()))

    @property
    def count(self) -> int:
        return len(self._connections)

    def conversation_ids(self) -> list[str]:
        return list(self._by_conversation)

    # ----------------------------------------------------------------- #
    # Delivery
    # ----------------------------------------------------------------- #
    async def send(self, connection_id: str, event: dict) -> bool:
        connection = self._connections.get(connection_id)
        if connection is None:
            return False
        return await self._write(connection, event)

    async def send_to_conversation(self, conversation_id: str, event: dict) -> int:
        """Fan out to every socket this process holds for the conversation.

        More than one is normal — the customer may have the site open in two
        tabs, and both should see the same assistant reply.
        """
        delivered = 0
        for connection_id in list(self._by_conversation.get(conversation_id, ())):
            if await self.send(connection_id, event):
                delivered += 1
        return delivered

    async def _write(self, connection: Connection, event: dict) -> bool:
        ws = connection.websocket
        if ws.client_state is not WebSocketState.CONNECTED:
            return False
        try:
            await ws.send_json(event)
            return True
        except Exception:  # noqa: BLE001 — a dead socket is normal, not an error
            log.debug("Send failed on %s; dropping", connection.connection_id, exc_info=True)
            return False

    # ----------------------------------------------------------------- #
    # Shutdown
    # ----------------------------------------------------------------- #
    async def drain(self, *, code: int = 1001, reason: str = "server shutting down") -> None:
        """Close every socket politely so clients reconnect elsewhere.

        Called during graceful shutdown — the design doc's "connection
        draining" (§19). Clients reconnect through the load balancer and land
        on a healthy instance, which restores state from durable storage.
        """
        for connection in list(self._connections.values()):
            try:
                await connection.websocket.close(code=code, reason=reason)
            except Exception:  # noqa: BLE001
                pass
        self._connections.clear()
        self._by_conversation.clear()
        self._by_session.clear()
