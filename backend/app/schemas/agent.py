"""Chat-agent DTOs for the REST fallback endpoint.

The WebSocket gateway has its own wire protocol in ``app/realtime/protocol.py``;
these are the request/response shapes for clients that cannot hold a socket.
"""

from pydantic import BaseModel


class AgentRequest(BaseModel):
    message: str
    # The conversation to continue. Named ``thread_id`` for backwards
    # compatibility; it is the ``conversation_id`` everywhere else.
    thread_id: str | None = None
    # Client-generated id, used as the idempotency key for the turn (§15).
    message_id: str | None = None
    # Guest session token minted by a previous call, so an anonymous visitor
    # keeps the identity the agent resolved for them.
    session_token: str | None = None
    # Accepted but ignored: identity is derived from the session server-side.
    # Kept so older clients do not get a 422.
    patient_id: int | None = None


class AgentResponse(BaseModel):
    thread_id: str
    final_text: str
    transcript: list[dict] = []
    tool_calls: list[dict] = []
    conversation_id: str = ""
    correlation_id: str = ""
    # Returned to anonymous callers so the next request continues the same
    # session (and therefore the same resolved identity).
    session_token: str = ""
    # Bookable slots the agent surfaced, read out of tool results server-side.
    options: list[dict] = []
    # The patient the server resolved for this session, if any.
    identity: dict | None = None
    duplicate: bool = False
    error: str = ""
