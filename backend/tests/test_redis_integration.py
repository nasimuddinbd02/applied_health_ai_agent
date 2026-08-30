"""The distributed paths, against a real Redis.

The rest of the suite runs Redis-disabled and covers the single-instance
fallbacks. These are the tests that actually prove the multi-server design:
one instance owns a socket, another instance's worker produces the reply, and
the reply arrives.

Skipped automatically when no Redis is listening.
"""

import asyncio
import uuid

import pytest

from app.core.config import Settings
from app.core.coordination import IdempotencyGuard
from app.messaging.event_bus import Handler  # noqa: F401  (documents the contract)
from app.messaging.events import Event, Topics
from app.messaging.redis_client import RedisClient
from app.messaging.redis_event_bus import RedisStreamEventBus
from app.realtime.connection_manager import Connection, ConnectionManager
from app.realtime.dispatcher import RealtimeDispatcher
from app.realtime.session_registry import SessionRegistry
from tests.test_realtime_transport import FakeWebSocket

pytestmark = pytest.mark.asyncio


def make_settings(namespace: str, server_id: str) -> Settings:
    return Settings(
        _env_file=None,
        redis_enabled=True,
        redis_namespace=namespace,
        server_id=server_id,
        event_consumer_group="test-workers",
        event_max_delivery_attempts=2,
        event_claim_idle_ms=60_000,
    )


@pytest.fixture
async def namespace():
    return f"cityhospital-it-{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def redis_a(namespace):
    settings = make_settings(namespace, "node-a")
    client = RedisClient(settings)
    if not await client.connect():
        pytest.skip("Redis is not reachable on REDIS_URL")
    yield client, settings
    # Remove everything this test wrote — the namespace is unique per test.
    raw = client.client()
    async for key in raw.scan_iter(match=f"{namespace}:*", count=500):
        await raw.delete(key)
    await client.close()


@pytest.fixture
async def redis_b(namespace, redis_a):
    """A second process's view of the same Redis."""
    settings = make_settings(namespace, "node-b")
    client = RedisClient(settings)
    await client.connect()
    yield client, settings
    await client.close()


# --------------------------------------------------------------------------- #
# Connection metadata is visible cluster-wide
# --------------------------------------------------------------------------- #
async def test_another_instance_can_find_the_socket_owner(redis_a, redis_b):
    client_a, settings_a = redis_a
    client_b, settings_b = redis_b

    await SessionRegistry(client_a, settings_a).register_connection(
        connection_id="c1", conversation_id="conv-1",
        session_id="guest-1", server_id="node-a",
    )

    owners = await SessionRegistry(client_b, settings_b).servers_for_conversation("conv-1")
    assert owners == {"node-a"}


async def test_a_session_identity_is_shared_between_instances(redis_a, redis_b):
    client_a, settings_a = redis_a
    client_b, settings_b = redis_b

    await SessionRegistry(client_a, settings_a).bind_patient("guest-1", 77, "Ada")
    session = await SessionRegistry(client_b, settings_b).get_session("guest-1")

    assert session["patient_id"] == "77"


async def test_an_idempotency_key_is_claimed_once_across_instances(redis_a, redis_b):
    client_a, settings_a = redis_a
    client_b, settings_b = redis_b

    assert await IdempotencyGuard(client_a, settings_a).claim("chat", "conv:m1") is True
    assert await IdempotencyGuard(client_b, settings_b).claim("chat", "conv:m1") is False


# --------------------------------------------------------------------------- #
# The event bus
# --------------------------------------------------------------------------- #
async def test_an_event_published_here_is_consumed_there(redis_a, redis_b):
    client_a, settings_a = redis_a
    client_b, settings_b = redis_b
    received: list[Event] = []
    stop = asyncio.Event()

    async def handler(event: Event) -> None:
        received.append(event)
        stop.set()

    consumer = RedisStreamEventBus(client_b, settings_b)
    task = asyncio.create_task(
        consumer.consume(Topics.CHAT_REQUESTED, handler, stop=stop, consumer_name="w1")
    )
    await asyncio.sleep(0.2)  # let the group be created before we publish

    await RedisStreamEventBus(client_a, settings_a).publish(
        Topics.CHAT_REQUESTED,
        Event(type=Topics.CHAT_REQUESTED, payload={"message": "hi"},
              conversation_id="conv-1", correlation_id="corr-1"),
    )

    await asyncio.wait_for(stop.wait(), timeout=10)
    task.cancel()

    assert received[0].payload["message"] == "hi"
    assert received[0].correlation_id == "corr-1"


async def test_a_poison_event_ends_up_in_the_dead_letter_stream(redis_a):
    client, settings = redis_a
    bus = RedisStreamEventBus(client, settings)
    attempts = []
    stop = asyncio.Event()

    async def always_fails(event: Event) -> None:
        attempts.append(event.attempts)
        raise ValueError("cannot handle this")

    task = asyncio.create_task(
        bus.consume(Topics.CHAT_REQUESTED, always_fails, stop=stop, consumer_name="w1")
    )
    await asyncio.sleep(0.2)
    await bus.publish(Topics.CHAT_REQUESTED, Event(type=Topics.CHAT_REQUESTED, payload={}))

    dlq = settings.stream(Topics.CHAT_REQUESTED) + ":dlq"
    for _ in range(100):
        if await client.client().xlen(dlq):
            break
        await asyncio.sleep(0.1)
    stop.set()
    task.cancel()

    assert await client.client().xlen(dlq) == 1
    assert attempts == [0, 1], "retried once, then dead-lettered"


# --------------------------------------------------------------------------- #
# The point of the whole exercise
# --------------------------------------------------------------------------- #
async def test_a_reply_produced_on_node_b_reaches_a_socket_held_by_node_a(redis_a, redis_b):
    """The design doc's step 7: route the answer to the pod that owns the socket."""
    client_a, settings_a = redis_a
    client_b, settings_b = redis_b

    # Node A: holds the customer's WebSocket.
    connections_a = ConnectionManager()
    registry_a = SessionRegistry(client_a, settings_a)
    dispatcher_a = RealtimeDispatcher(client_a, registry_a, connections_a, settings_a)
    socket = FakeWebSocket()
    await connections_a.add(Connection("c1", "conv-1", "guest-1", socket))
    await registry_a.register_connection(
        connection_id="c1", conversation_id="conv-1",
        session_id="guest-1", server_id="node-a",
    )
    await dispatcher_a.start()

    # Node B: runs the agent, holds no socket for this conversation.
    dispatcher_b = RealtimeDispatcher(
        client_b, SessionRegistry(client_b, settings_b), ConnectionManager(), settings_b
    )
    try:
        await dispatcher_b.dispatch("conv-1", {"type": "agent_message", "message": "booked"})

        for _ in range(100):
            if socket.sent:
                break
            await asyncio.sleep(0.05)
    finally:
        await dispatcher_a.stop()
        await dispatcher_b.stop()

    assert socket.sent == [{"type": "agent_message", "message": "booked"}]


async def test_an_event_for_an_unknown_conversation_is_simply_dropped(redis_b):
    """Nobody is connected: the reply is not an error, it is just not delivered.
    The customer sees it when they reconnect and replay history."""
    client_b, settings_b = redis_b
    dispatcher = RealtimeDispatcher(
        client_b, SessionRegistry(client_b, settings_b), ConnectionManager(), settings_b
    )
    assert await dispatcher.dispatch("conv-nobody", {"type": "agent_message"}) == 0
