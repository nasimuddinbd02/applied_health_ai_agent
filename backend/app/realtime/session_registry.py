"""Distributed connection & session metadata in Redis (design doc §6, §12).

Redis is *not* the WebSocket server. It answers one question — "which instance
currently owns the socket for this conversation?" — plus it holds the
short-lived chat session (who the visitor turned out to be). The socket itself
stays in ``ConnectionManager`` on the owning instance.

Keys
    ws:conn:{connection_id}    HASH  server_id, conversation_id, session_id   (TTL)
    ws:conv:{conversation_id}  SET   connection_ids                            (TTL)
    ws:server:{server_id}      SET   connection_ids                            (TTL)
    chat:session:{session_id}  HASH  kind, user_id, patient_id, patient_name   (TTL)

Records carry a TTL that the owning instance refreshes on every heartbeat, so
a pod that dies stops being advertised as an owner within one TTL window
instead of black-holing messages forever.
"""

import logging
import time

from app.core.config import Settings
from app.messaging.redis_client import RedisClient

log = logging.getLogger(__name__)


class _LocalStore:
    """Single-instance fallback used when Redis is down.

    It is deliberately not a "cache": it holds exactly what this process knows,
    which is correct for a one-instance deployment and honest (rather than
    silently wrong) for a multi-instance one.
    """

    def __init__(self) -> None:
        self.connections: dict[str, dict] = {}
        self.conversations: dict[str, set[str]] = {}
        self.sessions: dict[str, dict] = {}


class SessionRegistry:
    def __init__(self, redis: RedisClient, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings
        self._local = _LocalStore()

    @property
    def distributed(self) -> bool:
        return self._redis.available

    # ----------------------------------------------------------------- #
    # Key helpers
    # ----------------------------------------------------------------- #
    def _conn_key(self, connection_id: str) -> str:
        return self._settings.key("ws", "conn", connection_id)

    def _conv_key(self, conversation_id: str) -> str:
        return self._settings.key("ws", "conv", conversation_id)

    def _server_key(self, server_id: str) -> str:
        return self._settings.key("ws", "server", server_id)

    def _session_key(self, session_id: str) -> str:
        return self._settings.key("chat", "session", session_id)

    # ----------------------------------------------------------------- #
    # Connection routing
    # ----------------------------------------------------------------- #
    async def register_connection(self, *, connection_id: str, conversation_id: str,
                                  session_id: str, server_id: str) -> None:
        record = {
            "server_id": server_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "connected_at": str(int(time.time())),
        }
        if not self.distributed:
            self._local.connections[connection_id] = record
            self._local.conversations.setdefault(conversation_id, set()).add(connection_id)
            return
        ttl = self._settings.ws_registry_ttl_seconds
        try:
            pipe = self._redis.client().pipeline()
            pipe.hset(self._conn_key(connection_id), mapping=record)
            pipe.expire(self._conn_key(connection_id), ttl)
            pipe.sadd(self._conv_key(conversation_id), connection_id)
            pipe.expire(self._conv_key(conversation_id), ttl)
            pipe.sadd(self._server_key(server_id), connection_id)
            pipe.expire(self._server_key(server_id), ttl)
            await pipe.execute()
        except Exception:  # noqa: BLE001
            log.exception("Registry write failed; falling back to local routing")
            self._local.connections[connection_id] = record
            self._local.conversations.setdefault(conversation_id, set()).add(connection_id)

    async def heartbeat(self, *, connection_id: str, conversation_id: str,
                        server_id: str) -> None:
        """Refresh the TTLs. A pod that stops doing this is treated as gone."""
        if not self.distributed:
            return
        ttl = self._settings.ws_registry_ttl_seconds
        try:
            pipe = self._redis.client().pipeline()
            pipe.expire(self._conn_key(connection_id), ttl)
            pipe.expire(self._conv_key(conversation_id), ttl)
            pipe.expire(self._server_key(server_id), ttl)
            await pipe.execute()
        except Exception:  # noqa: BLE001
            log.debug("Registry heartbeat failed for %s", connection_id, exc_info=True)

    async def unregister_connection(self, *, connection_id: str, conversation_id: str,
                                    server_id: str) -> None:
        self._local.connections.pop(connection_id, None)
        conv = self._local.conversations.get(conversation_id)
        if conv is not None:
            conv.discard(connection_id)
            if not conv:
                self._local.conversations.pop(conversation_id, None)
        if not self.distributed:
            return
        try:
            pipe = self._redis.client().pipeline()
            pipe.delete(self._conn_key(connection_id))
            pipe.srem(self._conv_key(conversation_id), connection_id)
            pipe.srem(self._server_key(server_id), connection_id)
            await pipe.execute()
        except Exception:  # noqa: BLE001
            log.debug("Registry cleanup failed for %s", connection_id, exc_info=True)

    async def servers_for_conversation(self, conversation_id: str) -> set[str]:
        """Which instances currently hold a socket for this conversation."""
        if not self.distributed:
            local = self._local.conversations.get(conversation_id, set())
            return {
                self._local.connections[cid]["server_id"]
                for cid in local
                if cid in self._local.connections
            }
        try:
            client = self._redis.client()
            connection_ids = list(await client.smembers(self._conv_key(conversation_id)))
            if not connection_ids:
                return set()
            pipe = client.pipeline()
            for connection_id in connection_ids:
                pipe.hget(self._conn_key(connection_id), "server_id")
            owners = await pipe.execute()
            stale = [cid for cid, owner in zip(connection_ids, owners, strict=False) if not owner]
            if stale:
                # The owning pod's records expired — prune, so the set does not
                # grow forever with dead connections.
                await client.srem(self._conv_key(conversation_id), *stale)
            return {owner for owner in owners if owner}
        except Exception:  # noqa: BLE001
            log.exception("Registry lookup failed for conversation %s", conversation_id)
            return set()

    async def connection_count(self, server_id: str) -> int:
        if not self.distributed:
            return len(self._local.connections)
        try:
            return int(await self._redis.client().scard(self._server_key(server_id)))
        except Exception:  # noqa: BLE001
            return 0

    # ----------------------------------------------------------------- #
    # Chat session state (short-lived, coordination-only)
    # ----------------------------------------------------------------- #
    async def get_session(self, session_id: str) -> dict:
        if not self.distributed:
            return dict(self._local.sessions.get(session_id, {}))
        try:
            return await self._redis.client().hgetall(self._session_key(session_id)) or {}
        except Exception:  # noqa: BLE001
            return dict(self._local.sessions.get(session_id, {}))

    async def save_session(self, session_id: str, values: dict) -> None:
        clean = {k: str(v) for k, v in values.items() if v is not None}
        if not clean:
            return
        self._local.sessions[session_id] = {
            **self._local.sessions.get(session_id, {}), **clean
        }
        if not self.distributed:
            return
        try:
            ttl = self._settings.guest_session_expire_minutes * 60
            pipe = self._redis.client().pipeline()
            pipe.hset(self._session_key(session_id), mapping=clean)
            pipe.expire(self._session_key(session_id), ttl)
            await pipe.execute()
        except Exception:  # noqa: BLE001
            log.debug("Session write failed for %s", session_id, exc_info=True)

    async def bind_patient(self, session_id: str, patient_id: int, patient_name: str = "") -> None:
        """Record the patient this session turned out to be.

        Identity discovered by the agent (a name lookup, or a conversational
        registration) is bound **server-side** here — the browser is told about
        it, but never gets to assert it (§16).
        """
        await self.save_session(
            session_id, {"patient_id": patient_id, "patient_name": patient_name}
        )
