"""Appointment agent (class) — real LLM, no mocking.

A conversational assistant that collects the patient's needs (specialty/doctor +
reason), checks the doctor's availability, books an appointment, and confirms.

It is a LangGraph ``create_react_agent`` driven by the LLM factory's
ChatLiteLLM (OpenAI, with Anthropic/Gemini fallback), with tools loaded from the
FastMCP server via ``langchain-mcp-adapters``. A ``MemorySaver`` checkpointer
keyed by ``thread_id`` keeps multi-turn state.
"""

import uuid

from app.common.config import Settings
from app.common.prompts import PromptRegistry
from app.models.results import AgentResult
from app.providers.appointment_provider import AppointmentProvider
from app.providers.llm_factory import LLMFactory


class AgentProvider:
    def __init__(
        self,
        settings: Settings,
        appointments: AppointmentProvider,
        llm_factory: LLMFactory,
        prompts: PromptRegistry,
    ) -> None:
        self._settings = settings
        self._appt = appointments
        self._llm = llm_factory
        self._prompts = prompts
        self._cache: dict[str, object] = {}

    # ----------------------------------------------------------------- #
    # Public entry point
    # ----------------------------------------------------------------- #
    async def run(self, feature: str, user_message: str, *, thread_id: str | None = None,
                  max_steps: int = 10, patient_id: int | None = None) -> AgentResult:
        if not self._prompts.has_agent(feature):
            raise KeyError(f"Unknown agent feature: {feature}")
        tid = thread_id or uuid.uuid4().hex[:12]

        self._appt.log_chat(tid, patient_id, "patient", user_message)
        result = await self._run_langgraph(feature, user_message, tid, max_steps, patient_id)
        self._appt.log_chat(tid, patient_id, "agent", result.final_text)
        result.thread_id = tid
        return result

    # ----------------------------------------------------------------- #
    # LangGraph agent
    # ----------------------------------------------------------------- #
    async def _get_tools(self):
        if "tools" in self._cache:
            return self._cache["tools"]
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient(
            {"hospital": {"transport": self._settings.mcp_transport, "url": self._settings.mcp_url}}
        )
        tools = await client.get_tools()
        self._cache["tools"] = tools
        return tools

    async def _get_agent(self, feature: str):
        key = f"agent:{feature}"
        if key in self._cache:
            return self._cache[key]
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.prebuilt import create_react_agent

        tools = await self._get_tools()
        agent = create_react_agent(
            self._llm.get_llm(quality=True), tools,
            prompt=self._prompts.agent_prompt(feature), checkpointer=MemorySaver(),
        )
        self._cache[key] = agent
        return agent

    async def _run_langgraph(self, feature: str, user_message: str, thread_id: str,
                             max_steps: int, patient_id: int | None) -> AgentResult:
        agent = await self._get_agent(feature)
        cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": max_steps * 2}
        msg = user_message if patient_id is None else f"[patient_id={patient_id}] {user_message}"

        state = await agent.ainvoke({"messages": [("user", msg)]}, config=cfg)
        messages = state["messages"]

        transcript: list[dict] = []
        tool_calls: list[dict] = []
        tokens_in = tokens_out = 0
        for m in messages:
            usage = getattr(m, "usage_metadata", None) or {}
            tokens_in += int(usage.get("input_tokens", 0) or 0)
            tokens_out += int(usage.get("output_tokens", 0) or 0)
            for tc in getattr(m, "tool_calls", []) or []:
                tool_calls.append({"tool": tc["name"], "args": tc.get("args", {})})
            transcript.append({"type": m.__class__.__name__, "content": getattr(m, "content", "")})

        final_text = messages[-1].content if messages else ""
        return AgentResult(
            final_text=final_text, transcript=transcript, tool_calls=tool_calls,
            model=self._llm.model_string(quality=True),
            tokens_in=tokens_in, tokens_out=tokens_out,
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
        except Exception:
            return 0.0
