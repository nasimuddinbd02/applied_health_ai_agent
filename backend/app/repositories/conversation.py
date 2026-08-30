"""Durable conversation state (repository class).

The design doc's split (§12): *transport* state — who is connected, to which
pod — lives in Redis and dies with the socket. *Business* state — the
conversation, its turns, the workflow it is in — lives here, in the database,
and outlives any connection, pod or restart.
"""

from sqlmodel import select

from app.models import ChatMessage, Conversation, utcnow
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository):
    # ----------------------------------------------------------------- #
    # Conversations
    # ----------------------------------------------------------------- #
    def get(self, conversation_id: str) -> Conversation | None:
        with self._session() as s:
            return s.exec(
                select(Conversation).where(Conversation.conversation_id == conversation_id)
            ).first()

    def create(self, conversation_id: str, session_id: str,
               patient_id: int | None = None) -> Conversation:
        with self._session() as s:
            conversation = Conversation(
                conversation_id=conversation_id, session_id=session_id, patient_id=patient_id
            )
            s.add(conversation)
            s.commit()
            s.refresh(conversation)
            return conversation

    def update(self, conversation_id: str, **changes) -> Conversation | None:
        with self._session() as s:
            conversation = s.exec(
                select(Conversation).where(Conversation.conversation_id == conversation_id)
            ).first()
            if conversation is None:
                return None
            for field, value in changes.items():
                if value is not None and hasattr(conversation, field):
                    setattr(conversation, field, value)
            conversation.updated_at = utcnow()
            s.add(conversation)
            s.commit()
            s.refresh(conversation)
            return conversation

    def list_for_session(self, session_id: str) -> list[Conversation]:
        with self._session() as s:
            return list(
                s.exec(
                    select(Conversation)
                    .where(Conversation.session_id == session_id)
                    .order_by(Conversation.id.desc())
                ).all()
            )

    # ----------------------------------------------------------------- #
    # Messages
    # ----------------------------------------------------------------- #
    def add_message(self, conversation_id: str, patient_id: int | None, role: str,
                    content: str, *, message_id: str = "",
                    correlation_id: str = "") -> ChatMessage:
        with self._session() as s:
            message = ChatMessage(
                thread_id=conversation_id, patient_id=patient_id, role=role,
                content=content, message_id=message_id, correlation_id=correlation_id,
            )
            s.add(message)
            s.commit()
            s.refresh(message)
            return message

    def messages(self, conversation_id: str, limit: int | None = None) -> list[ChatMessage]:
        """Turns in chronological order; ``limit`` keeps the most recent ones."""
        with self._session() as s:
            query = select(ChatMessage).where(ChatMessage.thread_id == conversation_id)
            if limit:
                rows = list(s.exec(query.order_by(ChatMessage.id.desc()).limit(limit)).all())
                return list(reversed(rows))
            return list(s.exec(query.order_by(ChatMessage.id)).all())

    def message_exists(self, conversation_id: str, message_id: str) -> bool:
        """Has this exact client message already been recorded?

        The database-level half of duplicate protection — it still holds after
        the Redis idempotency key expires, or if Redis was down when the first
        copy arrived.
        """
        if not message_id:
            return False
        with self._session() as s:
            return (
                s.exec(
                    select(ChatMessage.id)
                    .where(ChatMessage.thread_id == conversation_id)
                    .where(ChatMessage.message_id == message_id)
                ).first()
                is not None
            )
