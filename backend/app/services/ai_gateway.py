"""AI Gateway — the single entry point for all LLM / agent calls.

Feature code depends only on ``get_llm`` / ``run_agent``; it never touches
LangChain / LangGraph / LiteLLM / MCP internals. Writes an ``AuditEvent`` for
every agent run — including failures, which is what makes "the pharmacy API
timed out" a visible event rather than a silent wrong answer (design doc §24).
"""

import asyncio
import time
from typing import Any

from app.core.config import Settings
from app.core.safety import SafetyGuard
from app.repositories.ai import AiRepository
from app.schemas.results import AgentResult
from app.services.agent import AgentEventHandler, AgentService
from app.services.llm import LLMFactory


class AIGatewayService:
    def __init__(
        self,
        settings: Settings,
        ai_repo: AiRepository,
        safety: SafetyGuard,
        llm_factory: LLMFactory,
        agent: AgentService,
    ) -> None:
        self._settings = settings
        self._ai = ai_repo
        self._safety = safety
        self._llm = llm_factory
        self._agent = agent

    # ----------------------------------------------------------------- #
    # Model client
    # ----------------------------------------------------------------- #
    def get_llm(self, *, quality: bool = True) -> Any:
        return self._llm.get_llm(quality=quality)

    # ----------------------------------------------------------------- #
    # Audit logging
    # ----------------------------------------------------------------- #
    def _log_audit(self, feature: str, model: str, *, tokens_in: int = 0, tokens_out: int = 0,
                   est_cost_usd: float = 0.0, outcome: str = "ok", summary: str = "",
                   latency_ms: int = 0) -> None:
        self._ai.add_audit_event(
            feature=feature, model=model, tokens_in=tokens_in, tokens_out=tokens_out,
            est_cost_usd=est_cost_usd, outcome=outcome, latency_ms=latency_ms,
            summary=self._safety.redact(summary)[:500],
        )

    # ----------------------------------------------------------------- #
    # run_agent()  — conversational appointment agent
    # ----------------------------------------------------------------- #
    async def run_agent(self, feature: str, user_message: str, *, thread_id: str,
                        history: list[dict] | None = None, max_steps: int = 8,
                        patient_id: int | None = None,
                        on_event: AgentEventHandler | None = None) -> AgentResult:
        """Run one agent turn.

        ``history`` is the durable transcript, supplied by the caller — the
        agent itself holds no state between turns, so any worker on any
        instance can serve any conversation.
        """
        started = time.perf_counter()
        try:
            result = await self._agent.run(
                feature, user_message, thread_id=thread_id, history=history,
                max_steps=max_steps, patient_id=patient_id, on_event=on_event,
            )
        except Exception as err:
            self._log_audit(
                feature, self._llm.model_string(quality=True), outcome="error",
                summary=f"{type(err).__name__}: {err}",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            raise

        self._log_audit(
            feature, result.model or self._llm.model_string(quality=True),
            tokens_in=result.tokens_in, tokens_out=result.tokens_out,
            est_cost_usd=result.est_cost_usd, outcome="agent", summary=result.final_text,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return result

    def run_agent_sync(self, feature: str, user_message: str, *, thread_id: str,
                       history: list[dict] | None = None, max_steps: int = 8,
                       patient_id: int | None = None) -> AgentResult:
        """Blocking wrapper for non-async callers (scripts, tests)."""
        return asyncio.run(self.run_agent(
            feature, user_message, thread_id=thread_id, history=history,
            max_steps=max_steps, patient_id=patient_id,
        ))
