"""Appointment agent (class) — real LLM, no mocking.

A conversational assistant that collects the patient's needs (specialty/doctor +
reason), checks the doctor's availability, books an appointment, and confirms.

It is a LangGraph ``create_react_agent`` driven by the LLM factory's
ChatLiteLLM (OpenAI, with Anthropic/Gemini fallback), with tools loaded from the
FastMCP server via ``langchain-mcp-adapters``.

Two things changed in the realtime renovation:

* **No in-process checkpointer.** Conversation state used to live in a
  ``MemorySaver`` keyed by thread id, which is exactly the "state only in
  process memory" the design doc warns against (§3, §13) — it dies with the
  pod and is invisible to every other instance. History is now passed in by
  the caller, which read it from Redis/SQLite, so any worker on any instance
  can continue any conversation.
* **It streams.** ``on_event`` is called as the agent works, so the customer
  sees "checking availability" rather than a spinner (§11).
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import Settings
from app.core.prompts import PromptRegistry
from app.schemas.results import AgentResult
from app.services.llm import LLMFactory

log = logging.getLogger(__name__)

AgentEventHandler = Callable[[str, dict], Awaitable[None]]


class AgentService:
    def __init__(self, settings: Settings, llm_factory: LLMFactory,
                 prompts: PromptRegistry) -> None:
        self._settings = settings
        self._llm = llm_factory
        self._prompts = prompts
        self._cache: dict[str, object] = {}

    # ----------------------------------------------------------------- #
    # Public entry point
    # ----------------------------------------------------------------- #
    async def run(self, feature: str, user_message: str, *, thread_id: str,
                  history: list[dict] | None = None, max_steps: int = 10,
                  patient_id: int | None = None,
                  on_event: AgentEventHandler | None = None) -> AgentResult:
        if not self._prompts.has_agent(feature):
            raise KeyError(f"Unknown agent feature: {feature}")
        result = await self._run_langgraph(
            feature, user_message, thread_id, max_steps, patient_id, history or [], on_event
        )
        result.thread_id = thread_id
        return result

    # ----------------------------------------------------------------- #
    # LangGraph agent
    # ----------------------------------------------------------------- #
    async def _get_tools(self):
        if "tools" in self._cache:
            return self._cache["tools"]
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient(
            {
                "hospital": {
                    "transport": self._settings.mcp_transport,
                    "url": self._settings.mcp_endpoint,
                }
            }
        )
        tools = await client.get_tools()
        self._cache["tools"] = tools
        return tools

    async def _get_agent(self, feature: str):
        key = f"agent:{feature}"
        if key in self._cache:
            return self._cache[key]
        from langgraph.prebuilt import create_react_agent

        tools = await self._get_tools()
        agent = create_react_agent(
            self._llm.get_llm(quality=True), tools,
            prompt=self._prompts.agent_prompt(feature),
        )
        self._cache[key] = agent
        return agent

    def _build_messages(self, history: list[dict], user_message: str,
                        patient_id: int | None) -> list[tuple[str, str]]:
        """Replay the durable transcript, then the new turn.

        ``patient_id`` is tagged onto the live message only — it is derived from
        the authenticated session on every turn, so a stale id can never be
        replayed out of history.
        """
        messages: list[tuple[str, str]] = []
        for turn in history:
            role = "assistant" if turn.get("role") == "agent" else "user"
            content = (turn.get("content") or "").strip()
            if content:
                messages.append((role, content))
        tagged = user_message if patient_id is None else f"[patient_id={patient_id}] {user_message}"
        messages.append(("user", tagged))
        return messages

    async def _run_langgraph(self, feature: str, user_message: str, thread_id: str,
                             max_steps: int, patient_id: int | None,
                             history: list[dict],
                             on_event: AgentEventHandler | None) -> AgentResult:
        agent = await self._get_agent(feature)
        cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": max_steps * 2}
        payload = {"messages": self._build_messages(history, user_message, patient_id)}

        collected: list[Any] = []
        try:
            async for chunk in agent.astream(payload, config=cfg, stream_mode="updates"):
                for node_update in (chunk or {}).values():
                    for message in (node_update or {}).get("messages", []) or []:
                        collected.append(message)
                        await self._emit(on_event, message)
        except Exception:
            log.exception("Streaming run failed for %s; retrying without streaming", thread_id)
            state = await agent.ainvoke(payload, config=cfg)
            collected = list(state.get("messages", []))

        return self._to_result(collected)

    async def _emit(self, on_event: AgentEventHandler | None, message: Any) -> None:
        """Turn one agent message into a progress event for the customer."""
        if on_event is None:
            return
        for call in getattr(message, "tool_calls", []) or []:
            await on_event("tool_call", {"tool": call.get("name", ""), "args": call.get("args", {})})
        if message.__class__.__name__ == "ToolMessage":
            await on_event(
                "tool_result",
                {"tool": getattr(message, "name", ""), "content": getattr(message, "content", "")},
            )

    def _to_result(self, messages: list[Any]) -> AgentResult:
        transcript: list[dict] = []
        tool_calls: list[dict] = []
        tool_results: list[dict] = []
        tokens_in = tokens_out = 0
        final_text = ""

        for message in messages:
            usage = getattr(message, "usage_metadata", None) or {}
            tokens_in += int(usage.get("input_tokens", 0) or 0)
            tokens_out += int(usage.get("output_tokens", 0) or 0)

            calls = getattr(message, "tool_calls", []) or []
            for call in calls:
                tool_calls.append({"tool": call["name"], "args": call.get("args", {})})

            content = getattr(message, "content", "")
            kind = message.__class__.__name__
            if kind == "ToolMessage":
                tool_results.append(
                    {"tool": getattr(message, "name", ""), "content": _as_text(content)}
                )
            elif kind == "AIMessage" and not calls and content:
                final_text = _as_text(content)

            transcript.append({"type": kind, "content": content})

        return AgentResult(
            final_text=final_text,
            transcript=transcript,
            tool_calls=tool_calls,
            tool_results=tool_results,
            model=self._llm.model_string(quality=True),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            est_cost_usd=self._estimate_cost(tokens_in, tokens_out),
        )

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        try:
            from litellm import cost_per_token

            in_c, out_c = cost_per_token(
                model=self._llm.model_string(quality=True),
                prompt_tokens=tokens_in, completion_tokens=tokens_out,
            )
            return round((in_c or 0.0) + (out_c or 0.0), 6)
        except Exception:  # noqa: BLE001 — pricing is best-effort telemetry
            return 0.0


def _as_text(content: Any) -> str:
    """Flatten LangChain content (str, or a list of content blocks) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ]
        return "".join(p for p in parts if p)
    return str(content or "")
