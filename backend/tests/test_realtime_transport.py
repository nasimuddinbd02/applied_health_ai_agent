"""Connection manager, session registry, idempotency and rate limiting.

These run with Redis disabled (see ``conftest``) so they cover the
single-instance fallbacks. ``test_redis_integration`` covers the distributed
paths against a real server.
"""

import asyncio

import pytest
from starlette.websockets import WebSocketState

from app.core.config import Settings
from app.core.coordination import IdempotencyGuard, RateLimiter
from app.messaging.redis_client import RedisClient
from app.realtime.connection_manager import Connection, ConnectionManager
from app.realtime.session_registry import SessionRegistry


class FakeWebSocket:
    """Minimal stand-in for a Starlette WebSocket."""

    def __init__(self, connected: bool = True) -> None:
        self.client_state = WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
        self.sent: list[dict] = []
        self.closed_with: tuple[int, str] | None = None
        self.fail = False

    async def send_json(self, payload: dict) -> None:
        if self.fail:
            raise ConnectionResetError("socket gone")
        self.sent.append(payload)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed_with = (code, reason)
        self.client_state = WebSocketState.DISCONNECTED


def make_connection(cid: str, conversation: str = "conv-1", session: str = "guest-1"):
    return Connection(cid, conversation, session, FakeWebSocket())


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, redis_enabled=False, server_id="test-node")


@pytest.fixture
def redis(settings) -> RedisClient:
    return RedisClient(settings)


# --------------------------------------------------------------------------- #
# ConnectionManager
# --------------------------------------------------------------------------- #
async def test_send_reaches_only_the_addressed_connection():
    manager = ConnectionManager()
    a, b = make_connection("c1"), make_connection("c2", conversation="conv-2")
    await manager.add(a)
    await manager.add(b)

    assert await manager.send("c1", {"type": "pong"}) is True
    assert a.websocket.sent == [{"type": "pong"}]
    assert b.websocket.sent == []


async def test_conversation_fan_out_hits_every_tab():
    """Two tabs, one conversation — both must see the assistant's reply."""
    manager = ConnectionManager()
    tab1, tab2 = make_connection("c1"), make_connection("c2")
    await manager.add(tab1)
    await manager.add(tab2)

    assert await manager.send_to_conversation("conv-1", {"type": "agent_message"}) == 2


async def test_a_dead_socket_is_not_counted_as_delivered():
    manager = ConnectionManager()
    connection = make_connection("c1")
    connection.websocket.fail = True
    await manager.add(connection)

    assert await manager.send_to_conversation("conv-1", {"type": "ping"}) == 0


async def test_remove_clears_every_index():
    manager = ConnectionManager()
    await manager.add(make_connection("c1"))
    await manager.remove("c1")

    assert manager.count == 0
    assert manager.conversation_ids() == []
    assert manager.session_connection_count("guest-1") == 0
    assert await manager.send("c1", {"type": "ping"}) is False


async def test_drain_closes_sockets_with_going_away():
    manager = ConnectionManager()
    connection = make_connection("c1")
    await manager.add(connection)

    await manager.drain()

    assert connection.websocket.closed_with[0] == 1001
    assert manager.count == 0


async def test_per_session_connection_count_limits_tabs():
    manager = ConnectionManager()
    await manager.add(make_connection("c1"))
    await manager.add(make_connection("c2"))
    assert manager.session_connection_count("guest-1") == 2


# --------------------------------------------------------------------------- #
# SessionRegistry (local fallback)
# --------------------------------------------------------------------------- #
async def test_registry_routes_a_conversation_to_its_owner(redis, settings):
    registry = SessionRegistry(redis, settings)
    await registry.register_connection(
        connection_id="c1", conversation_id="conv-1",
        session_id="guest-1", server_id="node-a",
    )
    assert await registry.servers_for_conversation("conv-1") == {"node-a"}


async def test_registry_forgets_a_closed_connection(redis, settings):
    registry = SessionRegistry(redis, settings)
    await registry.register_connection(
        connection_id="c1", conversation_id="conv-1",
        session_id="guest-1", server_id="node-a",
    )
    await registry.unregister_connection(
        connection_id="c1", conversation_id="conv-1", server_id="node-a"
    )
    assert await registry.servers_for_conversation("conv-1") == set()


async def test_binding_a_patient_is_readable_from_the_session(redis, settings):
    registry = SessionRegistry(redis, settings)
    await registry.bind_patient("guest-1", 42, "Ada Lovelace")

    session = await registry.get_session("guest-1")
    assert session["patient_id"] == "42"
    assert session["patient_name"] == "Ada Lovelace"


# --------------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------------- #
async def test_a_key_can_only_be_claimed_once(redis, settings):
    guard = IdempotencyGuard(redis, settings)
    assert await guard.claim("chat", "conv-1:msg-1") is True
    assert await guard.claim("chat", "conv-1:msg-1") is False


async def test_different_scopes_do_not_collide(redis, settings):
    guard = IdempotencyGuard(redis, settings)
    assert await guard.claim("chat", "same") is True
    assert await guard.claim("agent-run", "same") is True


async def test_release_lets_a_failed_operation_be_retried(redis, settings):
    guard = IdempotencyGuard(redis, settings)
    await guard.claim("chat", "k")
    await guard.release("chat", "k")
    assert await guard.claim("chat", "k") is True


async def test_an_expired_claim_can_be_taken_again(redis, settings):
    guard = IdempotencyGuard(redis, settings)
    assert await guard.claim("chat", "k", ttl=1) is True
    await asyncio.sleep(1.05)
    assert await guard.claim("chat", "k", ttl=1) is True


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #
async def test_messages_are_allowed_up_to_the_limit_then_refused(redis, settings):
    limiter = RateLimiter(redis, settings)
    allowed = [await limiter.allow("chat", "guest-1", limit=3, window=60) for _ in range(4)]
    assert allowed == [True, True, True, False]


async def test_each_session_has_its_own_budget(redis, settings):
    limiter = RateLimiter(redis, settings)
    for _ in range(3):
        await limiter.allow("chat", "noisy", limit=3, window=60)
    assert await limiter.allow("chat", "quiet", limit=3, window=60) is True
