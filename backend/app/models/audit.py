"""Operational audit trail: one row per AI/agent run."""

from sqlmodel import Field, SQLModel

from app.models.base import now_iso


class AuditEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: str = Field(default_factory=now_iso)
    feature: str = ""
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    est_cost_usd: float = 0.0
    outcome: str = ""
    summary: str = ""  # PII-redacted
