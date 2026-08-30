"""The event envelope carried on the bus, and the topic catalogue.

Every event carries a ``correlation_id`` that is minted when the customer's
message arrives on the WebSocket and then travels through the agent workflow,
the tool calls and the reply event — so one id ties the whole trace together
(design doc §18).
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


class Topics:
    """Bus topics. Redis Streams keys are derived from these."""

    CHAT_REQUESTED = "chat.user_message"      # gateway -> agent worker
    AGENT_COMPLETED = "agent.completed"       # agent worker -> analytics/audit
    AGENT_FAILED = "agent.failed"
    REFILL_REQUESTED = "refill.requested"     # long-running work -> background
    REFILL_COMPLETED = "refill.completed"

    ALL = (CHAT_REQUESTED, AGENT_COMPLETED, AGENT_FAILED, REFILL_REQUESTED, REFILL_COMPLETED)


@dataclass
class Event:
    """One immutable message on the bus.

    ``event_id`` makes consumers idempotent: the same event redelivered (Redis
    Streams / Kafka both guarantee *at least* once) must not act twice.
    """

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: new_id("evt"))
    correlation_id: str = ""
    conversation_id: str = ""
    session_id: str = ""
    origin_server_id: str = ""
    occurred_at: str = field(default_factory=_now_iso)
    attempts: int = 0

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.type,
                "payload": self.payload,
                "event_id": self.event_id,
                "correlation_id": self.correlation_id,
                "conversation_id": self.conversation_id,
                "session_id": self.session_id,
                "origin_server_id": self.origin_server_id,
                "occurred_at": self.occurred_at,
                "attempts": self.attempts,
            },
            default=str,
        )

    @classmethod
    def from_json(cls, raw: str) -> "Event":
        data = json.loads(raw)
        return cls(
            type=data.get("type", ""),
            payload=data.get("payload") or {},
            event_id=data.get("event_id") or new_id("evt"),
            correlation_id=data.get("correlation_id", ""),
            conversation_id=data.get("conversation_id", ""),
            session_id=data.get("session_id", ""),
            origin_server_id=data.get("origin_server_id", ""),
            occurred_at=data.get("occurred_at") or _now_iso(),
            attempts=int(data.get("attempts", 0) or 0),
        )
