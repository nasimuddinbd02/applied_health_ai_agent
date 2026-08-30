"""Reception controller: the front-desk today's-queue view.

Read-only endpoints for the queue + counters. The actual lifecycle actions
(check-in / checkout / cancel) are served by ``AppointmentController`` and are
already gated to the same staff roles.
"""

from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.services.reception import ReceptionService

_STAFF = Depends(require_role("receptionist", "admin", "doctor"))


class ReceptionController:
    def __init__(self, reception: ReceptionService) -> None:
        self._reception = reception
        self.router = APIRouter(prefix="/api/reception", tags=["reception"], dependencies=[_STAFF])
        self._register()

    def _register(self) -> None:
        r = self.router
        r.add_api_route("/queue", self.queue, methods=["GET"])
        r.add_api_route("/overview", self.overview, methods=["GET"])

    def queue(self):
        return self._reception.today_queue()

    def overview(self):
        return self._reception.overview()
