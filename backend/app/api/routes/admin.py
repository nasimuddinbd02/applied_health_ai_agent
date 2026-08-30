"""Admin controller: doctor onboarding, schedule generation, dashboard.

Every route is gated to the ``admin`` role — the front-desk/clinical roles use
the appointment + ops controllers instead.
"""

from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.schemas import DoctorCreate, DoctorUpdate, ScheduleTemplate
from app.services.admin import AdminService

_ADMIN = Depends(require_role("admin"))


class AdminController:
    def __init__(self, admin: AdminService) -> None:
        self._admin = admin
        self.router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[_ADMIN])
        self._register()

    def _register(self) -> None:
        r = self.router
        r.add_api_route("/overview", self.overview, methods=["GET"])
        r.add_api_route("/doctors", self.create_doctor, methods=["POST"])
        r.add_api_route("/doctors/{doctor_id}", self.update_doctor, methods=["PATCH"])
        r.add_api_route("/doctors/{doctor_id}/slots", self.list_slots, methods=["GET"])
        r.add_api_route("/doctors/{doctor_id}/schedule", self.generate_schedule, methods=["POST"])
        r.add_api_route("/slots/{slot_id}", self.delete_slot, methods=["DELETE"])

    def overview(self):
        return self._admin.overview()

    def create_doctor(self, body: DoctorCreate):
        profile = {
            "name": body.name, "specialty": body.specialty, "room": body.room,
            "bio": body.bio, "phone": body.phone, "consultation_fee": body.consultation_fee,
        }
        result = self._admin.create_doctor(profile, body.login_email, body.login_password)
        return {"doctor": result["doctor"], "login_email": result["login_email"]}

    def update_doctor(self, doctor_id: int, body: DoctorUpdate):
        return self._admin.update_doctor(doctor_id, body.model_dump(exclude_none=True))

    def list_slots(self, doctor_id: int):
        return self._admin.list_slots(doctor_id)

    def generate_schedule(self, doctor_id: int, body: ScheduleTemplate):
        return self._admin.generate_schedule(
            doctor_id, weekdays=body.weekdays, start_time=body.start_time,
            end_time=body.end_time, slot_minutes=body.slot_minutes,
            weeks=body.weeks, start_date=body.start_date,
        )

    def delete_slot(self, slot_id: int):
        self._admin.remove_slot(slot_id)
        return {"deleted": slot_id}
