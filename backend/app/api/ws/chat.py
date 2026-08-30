"""Chat gateway controller — the WebSocket endpoint at ``/ws/chat``.

The connection is established once (the load balancer picks this instance at
that moment and then stops choosing per frame, design doc §5), and this process
owns the socket for its lifetime. The handler does transport only: authenticate,
accept, register, read frames, write frames, heartbeat, clean up. Every business
decision belongs to ``ChatService`` and the agent worker.
"""

import asyncio
import contextlib
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.config import Settings
from app.realtime.connection_manager import Connection, ConnectionManager
from app.realtime.dispatcher import RealtimeDispatcher
from app.realtime.protocol import ClientMessage, ServerEvents
from app.realtime.session_registry import SessionRegistry
from app.realtime.ws_auth import ChatPrincipal, WebSocketAuthenticator
from app.services.chat import ChatRejected, ChatService
from app.services.conversation import ConversationService

log = logging.getLogger(__name__)

# Close codes (4000-4999 is the application-defined range).
CLOSE_TOO_MANY_CONNECTIONS = 4029
CLOSE_HEARTBEAT_TIMEOUT = 4008


class ChatWebSocketController:
    def __init__(self, settings: Settings, authenticator: WebSocketAuthenticator,
                 connections: ConnectionManager, registry: SessionRegistry,
                 dispatcher: RealtimeDispatcher, conversations: ConversationService,
                 chat: ChatService) -> None:
        self._settings = settings
        self._auth = authenticator
        self._connections = connections
        self._registry = registry
        self._dispatcher = dispatcher
        self._conversations = conversations
        self._chat = chat
        # connection_id -> monotonic time of the last pong, per instance.
        self._pong_at: dict[str, float] = {}
        self.router = APIRouter(tags=["chat-gateway"])
        self._register()

    def _register(self) -> None:
        self.router.add_api_websocket_route("/ws/chat", self.chat)

    # ----------------------------------------------------------------- #
    # Connection lifecycle
    # ----------------------------------------------------------------- #
    async def chat(self, websocket: WebSocket) -> None:
        principal = self._auth.authenticate(websocket)

        if self._connections.session_connection_count(principal.session_id) >= self._settings.ws_max_connections_per_session:
            await websocket.close(CLOSE_TOO_MANY_CONNECTIONS, "too many connections")
            return

        await websocket.accept()

        conversation = await self._conversations.resume_or_start(
            session_id=principal.session_id,
            conversation_id=websocket.query_params.get("conversation_id"),
            patient_id=principal.patient_id,
        )
        connection = Connection(
            connection_id=f"conn-{uuid.uuid4().hex[:16]}",
            conversation_id=conversation.conversation_id,
            session_id=principal.session_id,
            websocket=websocket,
        )

        await self._on_connect(connection, principal, conversation.patient_id)
        heartbeat = asyncio.create_task(
            self._heartbeat(connection), name=f"hb-{connection.connection_id}"
        )
        try:
            await self._read_loop(connection, principal)
        except WebSocketDisconnect:
            pass
        except Exception:  # noqa: BLE001
            log.exception("Chat socket %s failed", connection.connection_id)
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await heartbeat
            await self._on_disconnect(connection)

    async def _on_connect(self, connection: Connection, principal: ChatPrincipal,
                          patient_id: int | None) -> None:
        await self._connections.add(connection)
        await self._registry.register_connection(
            connection_id=connection.connection_id,
            conversation_id=connection.conversation_id,
            session_id=principal.session_id,
            server_id=self._dispatcher.server_id,
        )
        await self._registry.save_session(
            principal.session_id, principal.to_session_values()
        )

        session = await self._registry.get_session(principal.session_id)
        resolved = self._session_patient(session, patient_id or principal.patient_id)
        identity = None
        if resolved is not None:
            identity = {
                "patient_id": resolved,
                "name": session.get("patient_name") or principal.display_name,
            }

        await self._connections.send(connection.connection_id, ServerEvents.ready(
            conversation_id=connection.conversation_id,
            connection_id=connection.connection_id,
            server_id=self._dispatcher.server_id,
            session_token=principal.session_token,
            heartbeat_seconds=self._settings.ws_heartbeat_seconds,
            identity=identity,
        ))
        await self._send_history(connection)
        log.info(
            "Chat connected %s (conversation=%s, session=%s, live=%d)",
            connection.connection_id, connection.conversation_id,
            principal.session_id, self._connections.count,
        )

    async def _on_disconnect(self, connection: Connection) -> None:
        await self._connections.remove(connection.connection_id)
        await self._registry.unregister_connection(
            connection_id=connection.connection_id,
            conversation_id=connection.conversation_id,
            server_id=self._dispatcher.server_id,
        )
        log.info("Chat disconnected %s (live=%d)",
                 connection.connection_id, self._connections.count)

    # ----------------------------------------------------------------- #
    # Frames
    # ----------------------------------------------------------------- #
    async def _read_loop(self, connection: Connection, principal: ChatPrincipal) -> None:
        while True:
            raw = await connection.websocket.receive_text()
            if len(raw.encode("utf-8")) > self._settings.ws_max_message_bytes:
                await self._error(connection, "message_too_large",
                                  "Message exceeds the size limit.")
                continue
            try:
                frame = ClientMessage.model_validate_json(raw)
            except ValidationError:
                await self._error(connection, "bad_frame", "Unrecognised message.")
                continue

            if frame.type == "close":
                break
            if frame.type == "ping":
                await self._connections.send(connection.connection_id, ServerEvents.pong())
                continue
            if frame.type == "pong":
                self._pong_at[connection.connection_id] = time.monotonic()
                continue
            if frame.type == "resume":
                await self._send_history(connection)
                continue
            await self._on_user_message(connection, principal, frame)

    async def _on_user_message(self, connection: Connection, principal: ChatPrincipal,
                               frame: ClientMessage) -> None:
        text = frame.message
        if frame.type == "select_option":
            # A tapped slot chip is just another customer turn — the agent still
            # validates and books it, so the UI shortcut cannot bypass any rule.
            slot_id = (frame.option_id or "").removeprefix("slot-")
            if not slot_id.isdigit():
                await self._error(connection, "bad_option", "Unknown option.")
                return
            text = f"Please book slot {slot_id}."

        session = await self._registry.get_session(principal.session_id)
        patient_id = self._session_patient(session, principal.patient_id)

        try:
            accepted = await self._chat.submit(
                conversation_id=connection.conversation_id,
                session_id=principal.session_id,
                message=text,
                message_id=frame.message_id,
                patient_id=patient_id,
                server_id=self._dispatcher.server_id,
            )
        except ChatRejected as rejected:
            await self._error(connection, rejected.code, str(rejected),
                              message_id=frame.message_id,
                              retryable=rejected.code in ("rate_limited", "bus_unavailable"))
            return

        await self._connections.send(connection.connection_id, ServerEvents.ack(
            message_id=frame.message_id,
            conversation_id=connection.conversation_id,
            correlation_id=accepted.correlation_id,
            duplicate=accepted.duplicate,
        ))

    async def _send_history(self, connection: Connection) -> None:
        """Replay the durable transcript so a reconnect resumes mid-conversation."""
        turns = [
            {"role": m.role, "content": m.content, "created_at": m.created_at,
             "message_id": m.message_id}
            for m in self._conversations.transcript(connection.conversation_id)
        ]
        if turns:
            await self._connections.send(connection.connection_id, ServerEvents.history(
                conversation_id=connection.conversation_id, turns=turns,
            ))

    async def _error(self, connection: Connection, code: str, message: str, *,
                     message_id: str = "", retryable: bool = False) -> None:
        await self._connections.send(connection.connection_id, ServerEvents.error(
            code=code, message=message, conversation_id=connection.conversation_id,
            message_id=message_id, retryable=retryable,
        ))

    # ----------------------------------------------------------------- #
    # Heartbeat
    # ----------------------------------------------------------------- #
    async def _heartbeat(self, connection: Connection) -> None:
        """Ping the client, refresh the registry TTL, drop dead sockets.

        A TCP connection can stay "open" long after the peer is gone; without
        this the instance would keep advertising itself in Redis as the owner
        of a socket that will never deliver (design doc §17).
        """
        interval = self._settings.ws_heartbeat_seconds
        deadline = interval * (self._settings.ws_missed_heartbeats_allowed + 1)
        self._pong_at[connection.connection_id] = time.monotonic()
        try:
            while True:
                await asyncio.sleep(interval)
                last = self._pong_at.get(connection.connection_id, 0.0)
                if time.monotonic() - last > deadline:
                    log.info("Heartbeat timeout on %s", connection.connection_id)
                    with contextlib.suppress(Exception):
                        await connection.websocket.close(
                            CLOSE_HEARTBEAT_TIMEOUT, "heartbeat timeout"
                        )
                    return
                if not await self._connections.send(
                    connection.connection_id, ServerEvents.ping()
                ):
                    return
                await self._registry.heartbeat(
                    connection_id=connection.connection_id,
                    conversation_id=connection.conversation_id,
                    server_id=self._dispatcher.server_id,
                )
        except asyncio.CancelledError:
            raise
        finally:
            self._pong_at.pop(connection.connection_id, None)

    # ----------------------------------------------------------------- #
    # Helpers
    # ----------------------------------------------------------------- #
    @staticmethod
    def _session_patient(session: dict, fallback: int | None) -> int | None:
        raw = session.get("patient_id")
        if raw:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
        return fallback
