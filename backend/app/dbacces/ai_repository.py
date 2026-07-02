"""Ops data access (repository class): audit events for every AI/agent call."""

from sqlmodel import func, select

from app.dbacces.repository import BaseRepository
from app.models.entities import AuditEvent


class AiRepository(BaseRepository):
    def add_audit_event(self, **fields) -> AuditEvent:
        with self._session() as s:
            event = AuditEvent(**fields)
            s.add(event)
            s.commit()
            s.refresh(event)
            return event

    def list_audit_events(self) -> list[AuditEvent]:
        with self._session() as s:
            return list(s.exec(select(AuditEvent).order_by(AuditEvent.id.desc())).all())

    def audit_totals(self) -> dict:
        with self._session() as s:
            cost = s.exec(select(func.coalesce(func.sum(AuditEvent.est_cost_usd), 0.0))).one()
            tin = s.exec(select(func.coalesce(func.sum(AuditEvent.tokens_in), 0))).one()
            tout = s.exec(select(func.coalesce(func.sum(AuditEvent.tokens_out), 0))).one()
            return {
                "total_estimated_cost_usd": round(float(cost), 6),
                "total_tokens_in": int(tin),
                "total_tokens_out": int(tout),
            }
