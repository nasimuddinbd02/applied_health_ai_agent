"""Appointment-agent controller — the REST fallback for the chat gateway.

``/ws/chat`` is the primary transport. This endpoint stays for clients that
cannot hold a WebSocket (curl, tests, a proxy that strips upgrades) and runs
*exactly* the same turn: same validation, same idempotency, same durable
conversation, same worker. It just waits for the answer instead of streaming
it, so it gives up the progress events and the long-running-work story.

Identity works the way it does on the socket: derived from the bearer token, or
from a server-minted guest session — never from the request body (§16).
"""

from fastapi import APIRouter, Header

from app.core.config import Settings
from app.messaging.events import new_id
from app.realtime.session_registry import SessionRegistry
from app.realtime.ws_auth import WebSocketAuthenticator
from app.schemas import AgentRequest, AgentResponse
from app.services.appointment import AppointmentService
from app.services.chat import ChatRejected, ChatService
from app.services.conversation import ConversationService
from app.workers.agent_worker import AgentWorker


class AgentController:
    def __init__(self, chat: ChatService, conversations: ConversationService,
                 worker: AgentWorker, authenticator: WebSocketAuthenticator,
                 registry: SessionRegistry, appointments: AppointmentService,
                 settings: Settings) -> None:
        self._chat = chat
        self._conversations = conversations
        self._worker = worker
        self._auth = authenticator
        self._registry = registry
        self._appt = appointments
        self._settings = settings
        self.router = APIRouter(prefix="/api/agent", tags=["agent"])
        self._register()

    def _register(self) -> None:
        r = self.router
        r.add_api_route("/appointment", self.chat, methods=["POST"], response_model=AgentResponse)
        r.add_api_route("/appointment/{thread_id}/history", self.history, methods=["GET"])

    async def chat(
        self,
        req: AgentRequest,
        authorization: str | None = Header(default=None),
        x_chat_session: str | None = Header(default=None),
    ) -> AgentResponse:
        token = _bearer(authorization) or x_chat_session or req.session_token
        principal = self._auth.authenticate_token(token)

        conversation = await self._conversations.resume_or_start(
            session_id=principal.session_id,
            conversation_id=req.thread_id,
            patient_id=principal.patient_id,
        )
        await self._registry.save_session(
            principal.session_id, principal.to_session_values()
        )
        session = await self._registry.get_session(principal.session_id)
        patient_id = _as_int(session.get("patient_id")) or principal.patient_id

        try:
            _, event = await self._chat.accept(
                conversation_id=conversation.conversation_id,
                session_id=principal.session_id,
                message=req.message,
                message_id=req.message_id or new_id("msg"),
                patient_id=patient_id,
                server_id=self._settings.instance_id,
            )
        except ChatRejected as rejected:
            return AgentResponse(
                thread_id=conversation.conversation_id,
                conversation_id=conversation.conversation_id,
                session_token=principal.session_token,
                final_text=str(rejected),
                error=rejected.code,
            )

        if event is None:  # duplicate resend — replay the answer we already gave
            return self._replay(conversation.conversation_id, principal.session_token, patient_id)

        outcome = await self._worker.handle(event)
        return AgentResponse(
            thread_id=conversation.conversation_id,
            conversation_id=conversation.conversation_id,
            session_token=principal.session_token,
            correlation_id=outcome.correlation_id,
            final_text=outcome.final_text,
            transcript=outcome.transcript,
            tool_calls=outcome.tool_calls,
            options=outcome.options,
            identity=outcome.identity,
            error="agent_failed" if outcome.failed else "",
        )

    def history(self, thread_id: str):
        """The durable transcript. Unchanged shape — the table is the same one."""
        return self._appt.chat_history(thread_id)

    # ----------------------------------------------------------------- #
    # Helpers
    # ----------------------------------------------------------------- #
    def _replay(self, conversation_id: str, session_token: str,
                patient_id: int | None) -> AgentResponse:
        turns = self._conversations.transcript(conversation_id)
        last_agent = next((t for t in reversed(turns) if t.role == "agent"), None)
        return AgentResponse(
            thread_id=conversation_id,
            conversation_id=conversation_id,
            session_token=session_token,
            final_text=last_agent.content if last_agent else "",
            duplicate=True,
            identity={"patient_id": patient_id} if patient_id else None,
        )


def _bearer(header: str | None) -> str:
    if header and header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _as_int(value) -> int | None:
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None
