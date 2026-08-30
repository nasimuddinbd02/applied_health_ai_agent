"""Shared result dataclasses returned by the Gateway public functions."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    final_text: str
    transcript: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    # Raw tool output, kept separate from the transcript so the realtime layer
    # can lift structured results (a resolved patient, offered slots) out of it
    # server-side, instead of the browser scraping them from the transcript.
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    est_cost_usd: float = 0.0
    thread_id: str = ""
