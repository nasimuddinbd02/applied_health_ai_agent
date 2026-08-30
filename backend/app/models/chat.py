"""Durable conversation state for the realtime chat gateway.

The WebSocket connection is disposable transport; these rows are what a client
resumes from after a reconnect or a pod restart.
"""

from sqlmodel import Field, SQLModel

from app.models.base import now_iso


class Conversation(SQLModel, table=True):
    """The business-state half of a chat (as opposed to the transport half).

    ``conversation_id`` is the id the client holds and replays on reconnect;
    ``session_id`` is the authenticated (or guest) session that owns it, and is
    what authorises access to the transcript.
    """

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: str = Field(index=True, unique=True)
    session_id: str = Field(default="", index=True)
    patient_id: int | None = Field(default=None, foreign_key="patient.id")
    status: str = "active"  # active | closed
    workflow: str = ""  # booking | refill | ""
    workflow_status: str = ""  # e.g. awaiting_selection | completed
    last_correlation_id: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class ChatMessage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    thread_id: str = Field(index=True)  # == Conversation.conversation_id
    patient_id: int | None = Field(default=None, foreign_key="patient.id")
    role: str = "patient"  # patient | agent
    content: str = ""
    # Client-supplied id for the customer's turn, echoed on the agent's reply.
    # Doubles as the idempotency key that stops a resend replaying a workflow.
    message_id: str = Field(default="", index=True)
    correlation_id: str = ""
    created_at: str = Field(default_factory=now_iso)
