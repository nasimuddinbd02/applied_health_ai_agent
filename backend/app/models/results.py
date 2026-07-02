"""Shared result dataclasses returned by the Gateway public functions."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    final_text: str
    transcript: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    est_cost_usd: float = 0.0
    thread_id: str = ""
