"""Agent worker — consumes chat events, runs LangGraph, routes the reply back.

Run it inside the API process for local development
(``INLINE_AGENT_WORKER=true``, the default) or as its own deployment:

    python -m app.workers.agent_worker

Either way the code is identical, and that is the point: the worker reaches the
customer through ``RealtimeDispatcher``, which finds the instance that owns the
socket via Redis. It never assumes the socket is local, so scaling out is a
deployment change rather than a rewrite (design doc §6, §7, §25).
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field

from app.core.config import Settings
from app.core.coordination import IdempotencyGuard
from app.messaging.event_bus import EventBus
from app.messaging.events import Event, Topics
from app.realtime.dispatcher import RealtimeDispatcher
from app.realtime.protocol import TOOL_STATUS, ServerEvents
from app.realtime.session_registry import SessionRegistry
from app.realtime.tool_results import ToolResultReader
from app.services.ai_gateway import AIGatewayService
from app.services.conversation import ConversationService

log = logging.getLogger(__name__)


@dataclass
class TurnOutcome:
    """What one customer turn produced.

    The worker returns it so the REST fallback endpoint can answer in-band
    with exactly what the WebSocket path streamed out — one implementation of
    the turn, two transports.
    """

    conversation_id: str
    correlation_id: str
    final_text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    transcript: list[dict] = field(default_factory=list)
    options: list[dict] = field(default_factory=list)
    identity: dict | None = None
    patient_id: int | None = None
    duplicate: bool = False
    failed: bool = False


class AgentWorker:
    def __init__(self, bus: EventBus, gateway: AIGatewayService,
                 conversations: ConversationService, dispatcher: RealtimeDispatcher,
                 registry: SessionRegistry, idempotency: IdempotencyGuard,
                 settings: Settings) -> None:
        self._bus = bus
        self._gateway = gateway
        self._conversations = conversations
        self._dispatcher = dispatcher
        self._registry = registry
        self._idempotency = idempotency
        self._settings = settings
        self._reader = ToolResultReader()
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    def use_event_bus(self, bus: EventBus) -> None:
        self._bus = bus

    # ----------------------------------------------------------------- #
    # Lifecycle
    # ----------------------------------------------------------------- #
    async def start(self) -> None:
        if self._tasks:
            return
        self._stop.clear()
        for n in range(max(1, self._settings.agent_worker_concurrency)):
            self._tasks.append(
                asyncio.create_task(self._consume(n), name=f"agent-worker-{n}")
            )
        log.info(
            "Agent worker started (%d consumers, bus=%s)",
            len(self._tasks), self._bus.name,
        )

    async def _consume(self, index: int) -> None:
        consumer_name = f"{self._settings.instance_id}-{index}"
        try:
            await self._bus.consume(
                Topics.CHAT_REQUESTED, self.handle,
                stop=self._stop, consumer_name=consumer_name,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Consumer %s stopped unexpectedly", consumer_name)

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()

    # ----------------------------------------------------------------- #
    # One customer turn
    # ----------------------------------------------------------------- #
    async def handle(self, event: Event) -> TurnOutcome:
        conversation_id = event.conversation_id
        correlation_id = event.correlation_id
        payload = event.payload or {}
        message = payload.get("message", "")
        message_id = payload.get("message_id", "")

        # The bus is at-least-once: a redelivered event must not run the agent
        # (and therefore the booking tools) a second time.
        if not await self._idempotency.claim("agent-run", event.event_id):
            log.info("Skipping already-processed event %s", event.event_id)
            return TurnOutcome(conversation_id, correlation_id, duplicate=True)

        patient_id = await self._resolve_patient_id(event.session_id, payload.get("patient_id"))

        await self._send(conversation_id, ServerEvents.agent_status(
            status="thinking", conversation_id=conversation_id,
            correlation_id=correlation_id, message_id=message_id,
        ))

        try:
            result = await self._run_agent(
                event, message, message_id, correlation_id, patient_id
            )
        except Exception as err:  # noqa: BLE001
            await self._fail(event, err)
            return TurnOutcome(conversation_id, correlation_id, failed=True)

        return await self._publish_results(event, result, patient_id)

    async def _run_agent(self, event: Event, message: str, message_id: str,
                         correlation_id: str, patient_id: int | None):
        conversation_id = event.conversation_id
        history = await self._history_before(conversation_id, message)

        async def on_event(kind: str, data: dict) -> None:
            if kind != "tool_call":
                return
            status = TOOL_STATUS.get(data.get("tool", ""), "working")
            await self._send(conversation_id, ServerEvents.agent_status(
                status=status, conversation_id=conversation_id,
                correlation_id=correlation_id, message_id=message_id,
            ))

        return await self._gateway.run_agent(
            event.payload.get("feature", "appointment"), message,
            thread_id=conversation_id, history=history,
            patient_id=patient_id, on_event=on_event,
        )

    async def _publish_results(self, event: Event, result,
                               patient_id: int | None) -> TurnOutcome:
        conversation_id = event.conversation_id
        correlation_id = event.correlation_id
        message_id = (event.payload or {}).get("message_id", "")

        # Identity the agent resolved is bound to the session server-side, then
        # announced — the browser is told, it does not decide.
        identity = self._reader.identity(result.tool_results)
        if identity and identity["patient_id"] != patient_id:
            patient_id = identity["patient_id"]
            await self._registry.bind_patient(
                event.session_id, patient_id, identity.get("name", "")
            )
            self._conversations.bind_patient(conversation_id, patient_id)
            await self._send(conversation_id, ServerEvents.identity(
                patient_id=patient_id, name=identity.get("name", ""),
                conversation_id=conversation_id,
            ))

        options = self._reader.appointment_options(result.tool_results)
        if options:
            self._conversations.set_workflow(conversation_id, "booking", "awaiting_selection")
            await self._send(conversation_id, ServerEvents.appointment_options(
                options=options, conversation_id=conversation_id,
                correlation_id=correlation_id,
            ))
        elif self._reader.booked_appointment(result.tool_results):
            self._conversations.set_workflow(conversation_id, "booking", "completed")

        # Persist before notifying: if the socket is gone, the customer still
        # finds the reply waiting when they reconnect and replay history.
        await self._conversations.append_turn(
            conversation_id, role="agent", content=result.final_text,
            patient_id=patient_id, correlation_id=correlation_id,
        )
        await self._send(conversation_id, ServerEvents.agent_message(
            message=result.final_text, conversation_id=conversation_id,
            correlation_id=correlation_id, message_id=message_id,
            tool_calls=result.tool_calls,
        ))

        await self._emit_bus_event(Topics.AGENT_COMPLETED, event, {
            "message_id": message_id,
            "patient_id": patient_id,
            "tools_used": [c["tool"] for c in result.tool_calls],
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
        })

        return TurnOutcome(
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            final_text=result.final_text,
            tool_calls=result.tool_calls,
            transcript=result.transcript,
            options=options,
            identity=identity,
            patient_id=patient_id,
        )

    async def _fail(self, event: Event, err: Exception) -> None:
        """Report a failed turn instead of retrying it.

        A *crashed* worker is recovered by the bus (its unacked entries are
        reclaimed). A turn that raised is different: silently re-running it
        would re-call booking tools and post a second reply, so the customer is
        told and stays in control of the retry (design doc §24 — never claim
        success we do not have).
        """
        log.exception("Agent run failed for %s", event.conversation_id)
        await self._send(event.conversation_id, ServerEvents.error(
            code="agent_failed",
            message="Sorry — I could not complete that just now. Please try again.",
            conversation_id=event.conversation_id,
            correlation_id=event.correlation_id,
            message_id=(event.payload or {}).get("message_id", ""),
            retryable=True,
        ))
        await self._emit_bus_event(Topics.AGENT_FAILED, event, {"error": f"{type(err).__name__}"})

    # ----------------------------------------------------------------- #
    # Helpers
    # ----------------------------------------------------------------- #
    async def _resolve_patient_id(self, session_id: str, hinted: int | None) -> int | None:
        """Identity comes from the session, never from the wire.

        ``hinted`` is what the gateway derived when the message arrived; the
        session is re-read here because the agent may have identified the
        customer on an earlier turn handled by a different worker.
        """
        session = await self._registry.get_session(session_id)
        raw = session.get("patient_id")
        if raw:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
        return hinted

    async def _history_before(self, conversation_id: str, message: str) -> list[dict]:
        """Prior turns, excluding the message we are about to send in."""
        turns = list(await self._conversations.history(conversation_id))
        if turns and turns[-1].get("role") == "patient" and turns[-1].get("content") == message:
            turns.pop()
        return turns

    async def _send(self, conversation_id: str, event: dict) -> None:
        try:
            await self._dispatcher.dispatch(conversation_id, event)
        except Exception:  # noqa: BLE001 — the customer may simply have left
            log.debug("Dispatch failed for %s", conversation_id, exc_info=True)

    async def _emit_bus_event(self, topic: str, source: Event, payload: dict) -> None:
        try:
            await self._bus.publish(topic, Event(
                type=topic, payload=payload,
                conversation_id=source.conversation_id,
                session_id=source.session_id,
                correlation_id=source.correlation_id,
                origin_server_id=self._settings.instance_id,
            ))
        except Exception:  # noqa: BLE001 — telemetry must never fail a turn
            log.debug("Could not publish %s", topic, exc_info=True)


# --------------------------------------------------------------------------- #
# Standalone entry point
# --------------------------------------------------------------------------- #
async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    from app.core.container import container

    container.database.init()
    await container.redis.connect()
    container.select_event_bus()
    await container.dispatcher.start()
    await container.agent_worker.start()
    log.info("Agent worker ready (bus=%s)", container.event_bus.name)

    stop = asyncio.Event()
    try:
        await stop.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await container.agent_worker.stop()
        await container.dispatcher.stop()
        await container.redis.close()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_main())
