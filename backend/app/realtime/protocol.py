"""The WebSocket wire protocol (design doc §11).

Client -> Server            Server -> Client
  user_message                ready              handshake result + session token
  ping                        ack                message accepted (idempotency)
  resume                      agent_status       "checking_availability", ...
  select_option               agent_message      the assistant's reply
                              appointment_options
                              identity           patient the server resolved
                              history            replayed turns after a resume
                              error / pong

Two rules the rest of the code relies on:
  * the server never trusts a ``patient_id`` sent by the client — identity is
    derived from the authenticated session (§16);
  * every client message carries a ``message_id`` used as the idempotency key,
    so a reconnect-and-resend does not run the workflow twice (§15).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.messaging.events import new_id

CLIENT_MESSAGE_TYPES = ("user_message", "ping", "pong", "resume", "select_option", "close")


class ClientMessage(BaseModel):
    """A frame received from the browser. Unknown fields are rejected."""

    model_config = {"extra": "ignore"}

    type: Literal["user_message", "ping", "pong", "resume", "select_option", "close"]
    message_id: str = Field(default_factory=lambda: new_id("msg"))
    conversation_id: str | None = None
    message: str = ""
    option_id: str | None = None


class ServerEvents:
    """Builders for every server -> client frame.

    Keeping them in one place means the frontend contract is readable in a
    single screen, and no handler hand-rolls a dict.
    """

    @staticmethod
    def _base(event_type: str, *, conversation_id: str = "", correlation_id: str = "",
              message_id: str = "") -> dict[str, Any]:
        event: dict[str, Any] = {"type": event_type}
        if conversation_id:
            event["conversation_id"] = conversation_id
        if correlation_id:
            event["correlation_id"] = correlation_id
        if message_id:
            event["message_id"] = message_id
        return event

    @staticmethod
    def ready(*, conversation_id: str, connection_id: str, server_id: str,
              session_token: str, heartbeat_seconds: int, identity: dict | None) -> dict:
        return {
            **ServerEvents._base("ready", conversation_id=conversation_id),
            "connection_id": connection_id,
            "server_id": server_id,
            "session_token": session_token,
            "heartbeat_seconds": heartbeat_seconds,
            "identity": identity,
        }

    @staticmethod
    def ack(*, message_id: str, conversation_id: str, correlation_id: str,
            duplicate: bool = False) -> dict:
        return {
            **ServerEvents._base("ack", conversation_id=conversation_id,
                                 correlation_id=correlation_id, message_id=message_id),
            "duplicate": duplicate,
        }

    @staticmethod
    def agent_status(*, status: str, conversation_id: str = "", correlation_id: str = "",
                     message_id: str = "", detail: str = "") -> dict:
        event = ServerEvents._base("agent_status", conversation_id=conversation_id,
                                   correlation_id=correlation_id, message_id=message_id)
        event["status"] = status
        if detail:
            event["detail"] = detail
        return event

    @staticmethod
    def agent_message(*, message: str, conversation_id: str = "", correlation_id: str = "",
                      message_id: str = "", tool_calls: list[dict] | None = None) -> dict:
        event = ServerEvents._base("agent_message", conversation_id=conversation_id,
                                   correlation_id=correlation_id, message_id=message_id)
        event["message"] = message
        event["tool_calls"] = tool_calls or []
        return event

    @staticmethod
    def appointment_options(*, options: list[dict], conversation_id: str = "",
                            correlation_id: str = "") -> dict:
        event = ServerEvents._base("appointment_options", conversation_id=conversation_id,
                                   correlation_id=correlation_id)
        event["options"] = options
        return event

    @staticmethod
    def identity(*, patient_id: int, name: str, conversation_id: str = "") -> dict:
        event = ServerEvents._base("identity", conversation_id=conversation_id)
        event["patient_id"] = patient_id
        event["name"] = name
        return event

    @staticmethod
    def history(*, conversation_id: str, turns: list[dict]) -> dict:
        event = ServerEvents._base("history", conversation_id=conversation_id)
        event["turns"] = turns
        return event

    @staticmethod
    def error(*, code: str, message: str, conversation_id: str = "",
              correlation_id: str = "", message_id: str = "", retryable: bool = False) -> dict:
        event = ServerEvents._base("error", conversation_id=conversation_id,
                                   correlation_id=correlation_id, message_id=message_id)
        event["code"] = code
        event["message"] = message
        event["retryable"] = retryable
        return event

    @staticmethod
    def ping() -> dict:
        return {"type": "ping"}

    @staticmethod
    def pong() -> dict:
        return {"type": "pong"}


# Tool name -> the coarse status the customer sees while it runs. Statuses are
# deliberately vague about internals; they exist to keep the chat feeling live.
TOOL_STATUS = {
    "get_doctors": "finding_doctors",
    "find_doctors_by_specialty": "finding_doctors",
    "get_availability": "checking_availability",
    "book_appointment": "booking_appointment",
    "find_patient_by_name": "looking_up_your_record",
    "get_patient": "looking_up_your_record",
    "register_patient": "creating_your_record",
    "request_refill": "submitting_refill_request",
}
