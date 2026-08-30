"""Chat gateway business logic — everything the WebSocket handler must NOT do.

The handler's job is transport: accept, read frames, write frames. The moment a
customer message is parsed it comes here, which validates it, makes it
idempotent, persists it, and hands it to the event bus. The agent then runs on
a worker — possibly in another process, on another instance — so a slow LLM
call or a long-running refill never blocks the socket loop (design doc §3, §8).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.core.coordination import IdempotencyGuard, RateLimiter
from app.messaging.event_bus import EventBus
from app.messaging.events import Event, Topics, new_id
from app.services.conversation import ConversationService

log = logging.getLogger(__name__)


class ChatRejected(Exception):
    """A message that will not be processed. ``code`` is sent to the client."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ChatAccepted:
    """The gateway's answer to one customer message."""

    __slots__ = ("correlation_id", "duplicate")

    def __init__(self, correlation_id: str, duplicate: bool) -> None:
        self.correlation_id = correlation_id
        self.duplicate = duplicate


class ChatService:
    def __init__(self, conversations: ConversationService, bus: EventBus,
                 idempotency: IdempotencyGuard, rate_limiter: RateLimiter,
                 *, max_message_chars: int = 4000, feature: str = "appointment") -> None:
        self._conversations = conversations
        self._bus = bus
        self._idempotency = idempotency
        self._rate_limiter = rate_limiter
        self._max_message_chars = max_message_chars
        self._feature = feature
        self._degraded_runner: Callable[[Event], Awaitable[None]] | None = None

    def use_event_bus(self, bus: EventBus) -> None:
        """Swap the bus at startup, once we know whether Redis came up."""
        self._bus = bus

    def set_degraded_runner(self, runner: Callable[[Event], Awaitable[None]]) -> None:
        """Handler to run a turn in-process when the bus refuses the publish.

        Wired by the container to the agent worker. It is the last line of
        defence: Redis died mid-conversation, so the turn runs here instead of
        being dropped. Slower and unscheduled, but the customer gets an answer.
        """
        self._degraded_runner = runner

    @property
    def event_bus(self) -> EventBus:
        return self._bus

    # ----------------------------------------------------------------- #
    # Accept one customer message
    # ----------------------------------------------------------------- #
    async def accept(self, *, conversation_id: str, session_id: str, message: str,
                     message_id: str, patient_id: int | None,
                     server_id: str) -> tuple[ChatAccepted, Event | None]:
        """Validate, de-duplicate and persist one customer turn.

        Returns the event that should run the agent, or ``None`` when the turn
        was a duplicate and must not run again. Split out from ``submit`` so
        the synchronous REST fallback can run the same turn in-band instead of
        publishing it.
        """
        text = (message or "").strip()
        if not text:
            raise ChatRejected("empty_message", "Message cannot be empty.")
        if len(text) > self._max_message_chars:
            raise ChatRejected(
                "message_too_long",
                f"Message exceeds {self._max_message_chars} characters.",
            )
        if not await self._rate_limiter.allow("chat", session_id):
            raise ChatRejected("rate_limited", "Too many messages — please slow down.")

        correlation_id = new_id("corr")

        # Duplicate protection (§15). Redis answers instantly for the common
        # case; the database check catches a replay that outlived the key or
        # arrived while Redis was down.
        claimed = await self._idempotency.claim("chat", f"{conversation_id}:{message_id}")
        if not claimed or self._conversations.is_duplicate(conversation_id, message_id):
            log.info("Ignoring duplicate message %s on %s", message_id, conversation_id)
            return ChatAccepted(correlation_id, duplicate=True), None

        await self._conversations.append_turn(
            conversation_id, role="patient", content=text, patient_id=patient_id,
            message_id=message_id, correlation_id=correlation_id,
        )

        event = Event(
            type=Topics.CHAT_REQUESTED,
            payload={
                "feature": self._feature,
                "message": text,
                "message_id": message_id,
                "patient_id": patient_id,
            },
            conversation_id=conversation_id,
            session_id=session_id,
            correlation_id=correlation_id,
            origin_server_id=server_id,
        )
        return ChatAccepted(correlation_id, duplicate=False), event

    async def submit(self, *, conversation_id: str, session_id: str, message: str,
                     message_id: str, patient_id: int | None,
                     server_id: str) -> ChatAccepted:
        """Accept a turn and hand it to the event bus (the WebSocket path)."""
        accepted, event = await self.accept(
            conversation_id=conversation_id, session_id=session_id, message=message,
            message_id=message_id, patient_id=patient_id, server_id=server_id,
        )
        if event is None:
            return accepted
        try:
            await self._bus.publish(Topics.CHAT_REQUESTED, event)
        except Exception:  # noqa: BLE001
            log.exception("Event bus publish failed for %s", conversation_id)
            if self._degraded_runner is None:
                raise ChatRejected("bus_unavailable", "Could not queue the request.") from None
            # Run it here, but off the socket's read loop — the gateway must
            # stay responsive even while a degraded turn is in flight.
            asyncio.create_task(self._run_degraded(event))
        return accepted

    async def _run_degraded(self, event: Event) -> None:
        assert self._degraded_runner is not None
        try:
            await self._degraded_runner(event)
        except Exception:  # noqa: BLE001
            log.exception("Degraded in-process run failed for %s", event.conversation_id)
