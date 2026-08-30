"""The chat gateway end to end: WebSocket in, agent event out.

The LLM is stubbed at the gateway boundary (``AIGatewayService.run_agent``), so
these exercise the real socket handler, the real event bus, the real worker and
the real durable conversation — everything except the model call.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.core.container import container
from app.main import app
from app.messaging.events import Event, Topics
from app.schemas.results import AgentResult
from app.services.chat import ChatRejected

SLOTS = json.dumps([
    {"slot_id": 1, "doctor_id": 2, "starts_at": "2026-09-14T14:30:00", "duration_min": 30},
    {"slot_id": 2, "doctor_id": 2, "starts_at": "2026-09-14T16:00:00", "duration_min": 30},
])


def stub_result(text="I found two available times.", *, tool_results=None, tool_calls=None):
    return AgentResult(
        final_text=text,
        transcript=[{"type": "AIMessage", "content": text}],
        tool_calls=tool_calls or [{"tool": "get_availability", "args": {"doctor_id": 2}}],
        tool_results=tool_results or [{"tool": "get_availability", "content": SLOTS}],
        model="stub/model",
    )


@pytest.fixture
def stub_agent(monkeypatch):
    """Replace the model call; keep every other layer real."""
    calls = []

    async def fake_run_agent(feature, message, **kwargs):
        calls.append({"feature": feature, "message": message, **kwargs})
        if kwargs.get("on_event"):
            await kwargs["on_event"]("tool_call", {"tool": "get_availability", "args": {}})
        return stub_result()

    monkeypatch.setattr(container.gateway, "run_agent", fake_run_agent)
    return calls


def drain_until(ws, event_type, *, limit: int = 12) -> dict:
    """Read frames until ``event_type`` shows up (skipping heartbeats)."""
    for _ in range(limit):
        frame = ws.receive_json()
        if frame["type"] == event_type:
            return frame
    raise AssertionError(f"never received {event_type}")


# --------------------------------------------------------------------------- #
# Handshake
# --------------------------------------------------------------------------- #
def test_anonymous_visitor_gets_a_session_and_a_conversation(stub_agent):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ready = ws.receive_json()

    assert ready["type"] == "ready"
    assert ready["conversation_id"].startswith("conv-")
    assert ready["session_token"], "guest must be given a server-minted session token"
    assert ready["identity"] is None
    assert ready["heartbeat_seconds"] > 0


def test_the_same_guest_token_resumes_the_same_session(stub_agent):
    with TestClient(app) as client:
        with client.websocket_connect("/ws/chat") as ws:
            first = ws.receive_json()
        with client.websocket_connect(
            f"/ws/chat?token={first['session_token']}"
            f"&conversation_id={first['conversation_id']}"
        ) as ws:
            second = ws.receive_json()

    assert second["conversation_id"] == first["conversation_id"]


def test_a_forged_conversation_id_does_not_leak_a_transcript(stub_agent):
    """Someone else's conversation id must silently start a new conversation."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/chat") as victim:
            stolen = victim.receive_json()["conversation_id"]
        with client.websocket_connect(f"/ws/chat?conversation_id={stolen}") as attacker:
            ready = attacker.receive_json()

    assert ready["conversation_id"] != stolen


# --------------------------------------------------------------------------- #
# A full turn
# --------------------------------------------------------------------------- #
def test_a_message_is_acked_then_answered(stub_agent):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # ready
        ws.send_json({"type": "user_message", "message_id": "msg-1",
                      "message": "Can I move my appointment to Monday?"})

        ack = drain_until(ws, "ack")
        assert ack["message_id"] == "msg-1"
        assert ack["duplicate"] is False
        assert ack["correlation_id"].startswith("corr-")

        status = drain_until(ws, "agent_status")
        assert status["status"] in ("thinking", "checking_availability")

        options = drain_until(ws, "appointment_options")
        assert [o["id"] for o in options["options"]] == ["slot-1", "slot-2"]

        reply = drain_until(ws, "agent_message")
        assert reply["message"] == "I found two available times."
        assert reply["correlation_id"] == ack["correlation_id"]


def test_the_agent_never_receives_a_client_supplied_patient_id(stub_agent):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()
        ws.send_json({"type": "user_message", "message_id": "msg-1",
                      "message": "book me in", "patient_id": 999})
        drain_until(ws, "agent_message")

    assert stub_agent[0]["patient_id"] is None


def test_resending_a_message_id_does_not_run_the_agent_twice(stub_agent):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()
        payload = {"type": "user_message", "message_id": "msg-dup", "message": "hello"}
        ws.send_json(payload)
        drain_until(ws, "agent_message")
        ws.send_json(payload)
        second_ack = drain_until(ws, "ack")

    assert second_ack["duplicate"] is True
    assert len(stub_agent) == 1


def test_reconnecting_replays_the_durable_transcript(stub_agent):
    with TestClient(app) as client:
        with client.websocket_connect("/ws/chat") as ws:
            ready = ws.receive_json()
            ws.send_json({"type": "user_message", "message_id": "msg-1", "message": "hello"})
            drain_until(ws, "agent_message")

        # The socket is gone; the conversation is not.
        with client.websocket_connect(
            f"/ws/chat?token={ready['session_token']}"
            f"&conversation_id={ready['conversation_id']}"
        ) as ws:
            ws.receive_json()  # ready
            history = drain_until(ws, "history")

    roles = [t["role"] for t in history["turns"]]
    assert roles == ["patient", "agent"]
    assert history["turns"][0]["content"] == "hello"


def test_the_agent_is_given_the_earlier_turns(stub_agent):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()
        ws.send_json({"type": "user_message", "message_id": "m1", "message": "first"})
        drain_until(ws, "agent_message")
        ws.send_json({"type": "user_message", "message_id": "m2", "message": "second"})
        drain_until(ws, "agent_message")

    assert stub_agent[0]["history"] == []
    assert [t["content"] for t in stub_agent[1]["history"]] == [
        "first", "I found two available times."
    ]


def test_identity_resolved_by_the_agent_is_announced(monkeypatch):
    async def fake_run_agent(feature, message, **kwargs):
        return stub_result(
            "You're all set, Ada.",
            tool_results=[{"tool": "register_patient",
                           "content": '{"patient_id": 4242, "name": "Ada Lovelace"}'}],
        )

    monkeypatch.setattr(container.gateway, "run_agent", fake_run_agent)

    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()
        ws.send_json({"type": "user_message", "message_id": "m1", "message": "I'm new here"})
        identity = drain_until(ws, "identity")

    assert identity == {"type": "identity", "conversation_id": identity["conversation_id"],
                        "patient_id": 4242, "name": "Ada Lovelace"}


def test_a_failed_agent_run_reports_an_error_instead_of_a_fake_answer(monkeypatch):
    async def boom(feature, message, **kwargs):
        raise RuntimeError("pharmacy API timed out")

    monkeypatch.setattr(container.gateway, "run_agent", boom)

    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()
        ws.send_json({"type": "user_message", "message_id": "m1", "message": "refill please"})
        error = drain_until(ws, "error")

    assert error["code"] == "agent_failed"
    assert error["retryable"] is True


# --------------------------------------------------------------------------- #
# Transport rules
# --------------------------------------------------------------------------- #
def test_ping_is_answered_with_pong(stub_agent):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()
        ws.send_json({"type": "ping"})
        assert drain_until(ws, "pong")["type"] == "pong"


def test_an_unparseable_frame_is_rejected_without_dropping_the_socket(stub_agent):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()
        ws.send_text('{"type": "nonsense"}')
        assert drain_until(ws, "error")["code"] == "bad_frame"

        ws.send_json({"type": "ping"})
        assert drain_until(ws, "pong")["type"] == "pong"


def test_an_oversized_message_is_refused(stub_agent):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()
        ws.send_json({"type": "user_message", "message": "x" * 20_000})
        assert drain_until(ws, "error")["code"] == "message_too_large"


def test_selecting_a_slot_becomes_an_ordinary_turn(stub_agent):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()
        ws.send_json({"type": "select_option", "message_id": "m1", "option_id": "slot-7"})
        drain_until(ws, "agent_message")

    assert stub_agent[0]["message"] == "Please book slot 7."


def test_a_bogus_option_id_is_refused(stub_agent):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()
        ws.send_json({"type": "select_option", "message_id": "m1",
                      "option_id": "slot-7; DROP TABLE"})
        assert drain_until(ws, "error")["code"] == "bad_option"


# --------------------------------------------------------------------------- #
# ChatService rules, without a socket
# --------------------------------------------------------------------------- #
async def test_an_empty_message_is_rejected():
    with pytest.raises(ChatRejected) as err:
        await container.chat.accept(
            conversation_id="conv-x", session_id="guest-x", message="   ",
            message_id="m1", patient_id=None, server_id="node-a",
        )
    assert err.value.code == "empty_message"


async def test_the_rate_limit_stops_a_flood():
    limit = container.settings.chat_rate_limit_messages
    conversation = await container.conversations.resume_or_start(
        session_id="guest-flood", conversation_id=None
    )
    for i in range(limit):
        await container.chat.accept(
            conversation_id=conversation.conversation_id, session_id="guest-flood",
            message=f"m{i}", message_id=f"m{i}", patient_id=None, server_id="node-a",
        )
    with pytest.raises(ChatRejected) as err:
        await container.chat.accept(
            conversation_id=conversation.conversation_id, session_id="guest-flood",
            message="one more", message_id="m-extra", patient_id=None, server_id="node-a",
        )
    assert err.value.code == "rate_limited"


async def test_an_accepted_turn_is_published_as_a_chat_event():
    conversation = await container.conversations.resume_or_start(
        session_id="guest-pub", conversation_id=None
    )
    _, event = await container.chat.accept(
        conversation_id=conversation.conversation_id, session_id="guest-pub",
        message="hello", message_id="m1", patient_id=None, server_id="node-a",
    )
    assert isinstance(event, Event)
    assert event.type == Topics.CHAT_REQUESTED
    assert event.payload["message"] == "hello"
    assert event.correlation_id.startswith("corr-")


# --------------------------------------------------------------------------- #
# The REST fallback runs the same turn
# --------------------------------------------------------------------------- #
def test_rest_fallback_answers_in_band_and_returns_a_session(stub_agent):
    with TestClient(app) as client:
        res = client.post("/api/agent/appointment", json={"message": "book me in"})

    body = res.json()
    assert res.status_code == 200
    assert body["final_text"] == "I found two available times."
    assert body["conversation_id"].startswith("conv-")
    assert body["session_token"], "an anonymous caller must get a session token back"
    assert [o["id"] for o in body["options"]] == ["slot-1", "slot-2"]


def test_rest_fallback_keeps_the_conversation_across_calls(stub_agent):
    with TestClient(app) as client:
        first = client.post("/api/agent/appointment", json={"message": "hello"}).json()
        second = client.post("/api/agent/appointment", json={
            "message": "cardiology please",
            "thread_id": first["conversation_id"],
            "session_token": first["session_token"],
        }).json()

    assert second["conversation_id"] == first["conversation_id"]
    assert [t["content"] for t in stub_agent[1]["history"]] == [
        "hello", "I found two available times."
    ]


def test_rest_fallback_ignores_a_client_supplied_patient_id(stub_agent):
    with TestClient(app) as client:
        client.post("/api/agent/appointment", json={"message": "hi", "patient_id": 999})

    assert stub_agent[0]["patient_id"] is None


def test_rest_fallback_replays_rather_than_repeating_a_duplicate(stub_agent):
    with TestClient(app) as client:
        first = client.post("/api/agent/appointment", json={
            "message": "hello", "message_id": "rest-dup",
        }).json()
        again = client.post("/api/agent/appointment", json={
            "message": "hello", "message_id": "rest-dup",
            "thread_id": first["conversation_id"],
            "session_token": first["session_token"],
        }).json()

    assert again["duplicate"] is True
    assert again["final_text"] == first["final_text"]
    assert len(stub_agent) == 1
