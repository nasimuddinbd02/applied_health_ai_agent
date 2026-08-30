"""Conversation business logic: ownership, history, workflow state.

This is what makes a chat survive its connection. A pod dies, the browser
reconnects through the load balancer to a different pod, and that pod calls
``history()`` here to carry on exactly where the customer left off (design doc
§13) — no state was in the dead process.
"""

import uuid

from app.models import Conversation
from app.repositories.conversation import ConversationRepository
from app.repositories.conversation_cache import ConversationCache


class ConversationError(Exception):
    """Raised when a session asks for a conversation that is not its own."""


class ConversationService:
    def __init__(self, repo: ConversationRepository, cache: ConversationCache,
                 history_turns: int = 20) -> None:
        self._repo = repo
        self._cache = cache
        self._history_turns = history_turns

    # ----------------------------------------------------------------- #
    # Lifecycle
    # ----------------------------------------------------------------- #
    @staticmethod
    def new_conversation_id() -> str:
        return f"conv-{uuid.uuid4().hex[:16]}"

    async def resume_or_start(self, *, session_id: str, conversation_id: str | None,
                              patient_id: int | None = None) -> Conversation:
        """Return the client's conversation, or start a fresh one.

        A ``conversation_id`` the client offers is honoured only if the record
        belongs to their session. Anything else — unknown id, someone else's id
        — silently starts a new conversation rather than leaking a transcript.
        """
        if conversation_id:
            existing = self._repo.get(conversation_id)
            if existing is not None and existing.session_id == session_id:
                if patient_id and existing.patient_id != patient_id:
                    return self._repo.update(conversation_id, patient_id=patient_id) or existing
                return existing
        return self._repo.create(self.new_conversation_id(), session_id, patient_id)

    def get_owned(self, conversation_id: str, session_id: str) -> Conversation:
        conversation = self._repo.get(conversation_id)
        if conversation is None or conversation.session_id != session_id:
            raise ConversationError("Conversation not found.")
        return conversation

    def get(self, conversation_id: str) -> Conversation | None:
        return self._repo.get(conversation_id)

    # ----------------------------------------------------------------- #
    # Turns
    # ----------------------------------------------------------------- #
    async def append_turn(self, conversation_id: str, *, role: str, content: str,
                          patient_id: int | None = None, message_id: str = "",
                          correlation_id: str = "") -> None:
        self._repo.add_message(
            conversation_id, patient_id, role, content,
            message_id=message_id, correlation_id=correlation_id,
        )
        await self._cache.append(conversation_id, {"role": role, "content": content})
        self._repo.update(conversation_id, last_correlation_id=correlation_id or None)

    async def history(self, conversation_id: str) -> list[dict]:
        """Recent turns as ``{"role", "content"}``, newest last.

        Redis first, database on a miss — and the miss re-primes the cache so
        the pod that just took over a conversation is fast from its second
        message onward.
        """
        cached = await self._cache.recent(conversation_id)
        if cached is not None:
            return cached
        turns = [
            {"role": m.role, "content": m.content}
            for m in self._repo.messages(conversation_id, limit=self._history_turns)
        ]
        await self._cache.prime(conversation_id, turns)
        return turns

    def transcript(self, conversation_id: str) -> list:
        """The full durable transcript (used by the resume/history endpoints)."""
        return self._repo.messages(conversation_id)

    def is_duplicate(self, conversation_id: str, message_id: str) -> bool:
        return self._repo.message_exists(conversation_id, message_id)

    # ----------------------------------------------------------------- #
    # Identity & workflow
    # ----------------------------------------------------------------- #
    def bind_patient(self, conversation_id: str, patient_id: int) -> Conversation | None:
        return self._repo.update(conversation_id, patient_id=patient_id)

    def set_workflow(self, conversation_id: str, workflow: str,
                     status: str = "") -> Conversation | None:
        return self._repo.update(
            conversation_id, workflow=workflow, workflow_status=status or None
        )

    def close(self, conversation_id: str) -> Conversation | None:
        return self._repo.update(conversation_id, status="closed")
