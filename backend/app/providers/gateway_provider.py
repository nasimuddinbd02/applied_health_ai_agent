"""AI Gateway — the single entry point for all LLM / agent calls.

Feature code depends only on ``get_llm`` / ``run_agent``; it never touches
LangChain / LangGraph / LiteLLM / MCP internals. Writes an ``AuditEvent`` for
every agent run. Degrades to deterministic offline behaviour when
``settings.offline`` is true.
"""

import asyncio
from typing import Any

from app.common.config import Settings
from app.dbacces.ai_repository import AiRepository
from app.lib.safety import SafetyGuard
from app.models.results import AgentResult
from app.providers.agent_provider import AgentProvider
from app.providers.llm_factory import LLMFactory


class GatewayProvider:
    def __init__(
        self,
        settings: Settings,
        ai_repo: AiRepository,
        safety: SafetyGuard,
        llm_factory: LLMFactory,
        agent: AgentProvider,
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
                   est_cost_usd: float = 0.0, outcome: str = "ok", summary: str = "") -> None:
        self._ai.add_audit_event(
            feature=feature, model=model, tokens_in=tokens_in, tokens_out=tokens_out,
            est_cost_usd=est_cost_usd, outcome=outcome,
            summary=self._safety.redact(summary)[:500],
        )

    # ----------------------------------------------------------------- #
    # run_agent()  — conversational appointment agent
    # ----------------------------------------------------------------- #
    async def run_agent(self, feature: str, user_message: str, *, thread_id: str | None = None,
                        max_steps: int = 8, patient_id: int | None = None) -> AgentResult:
        """Async-native agent run: awaited directly from async routes so the
        event loop is never blocked (and no loop juggling is needed)."""
        result = await self._agent.run(
            feature, user_message, thread_id=thread_id, max_steps=max_steps, patient_id=patient_id
        )
        model = result.model or self._llm.model_string(quality=True)
        self._log_audit(feature, model, tokens_in=result.tokens_in, tokens_out=result.tokens_out,
                        est_cost_usd=result.est_cost_usd, outcome="agent", summary=result.final_text)
        return result

    def run_agent_sync(self, feature: str, user_message: str, *, thread_id: str | None = None,
                       max_steps: int = 8, patient_id: int | None = None) -> AgentResult:
        """Blocking wrapper for non-async callers (scripts, tests)."""
        return asyncio.run(self.run_agent(
            feature, user_message, thread_id=thread_id, max_steps=max_steps, patient_id=patient_id
        ))
