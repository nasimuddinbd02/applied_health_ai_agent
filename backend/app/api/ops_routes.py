"""Ops controller: audit log + cost (every agent call is recorded)."""

from fastapi import APIRouter, Depends

from app.dbacces.ai_repository import AiRepository
from app.lib.authz import require_role
from app.providers.appointment_provider import AppointmentProvider

_STAFF = Depends(require_role("doctor", "receptionist", "admin"))


class OpsController:
    def __init__(self, ai_repo: AiRepository, appointments: AppointmentProvider) -> None:
        self._ai = ai_repo
        self._appt = appointments
        self.router = APIRouter(prefix="/api", tags=["ops"])
        self._register()

    def _register(self) -> None:
        self.router.add_api_route(
            "/audit", self.audit_log, methods=["GET"],
            dependencies=[Depends(require_role("admin"))],
        )
        self.router.add_api_route(
            "/refill-requests", self.refill_requests, methods=["GET"],
            dependencies=[_STAFF],
        )

    def audit_log(self):
        events = self._ai.list_audit_events()
        totals = self._ai.audit_totals()
        return {**totals, "count": len(events), "events": events}

    def refill_requests(self):
        return self._appt.list_refill_requests()
