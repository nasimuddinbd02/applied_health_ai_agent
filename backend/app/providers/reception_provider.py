"""Front-desk (receptionist) business logic: today's appointment queue.

Read-aggregation over the existing appointment data — joins each of today's
appointments with the patient and doctor names the front desk needs, and
reports a small set of queue counters.
"""

from app.dbacces.domain_repository import DomainRepository
from app.models.entities import today_iso

# Appointment statuses that still need front-desk / clinical action today.
_ACTIVE = ("booked", "checked_in", "in_treatment")


class ReceptionProvider:
    def __init__(self, domain_repo: DomainRepository) -> None:
        self._domain = domain_repo

    def _today_appointments(self) -> list:
        return self._domain.list_appointments_on(today_iso())

    def today_queue(self) -> list[dict]:
        """Every appointment scheduled for today, enriched with patient/doctor
        names and ordered by start time — the front-desk work list."""
        patients = {p.id: p.name for p in self._domain.list_patients()}
        doctors = {d.id: d for d in self._domain.list_doctors()}
        rows: list[dict] = []
        for a in self._today_appointments():
            doctor = doctors.get(a.doctor_id)
            rows.append({
                "appointment_id": a.id,
                "starts_at": a.starts_at,
                "duration_min": a.duration_min,
                "status": a.status,
                "reason": a.reason,
                "patient_id": a.patient_id,
                "patient_name": patients.get(a.patient_id, f"Patient #{a.patient_id}"),
                "doctor_id": a.doctor_id,
                "doctor_name": doctor.name if doctor else f"Doctor #{a.doctor_id}",
                "room": doctor.room if doctor else "",
            })
        rows.sort(key=lambda r: r["starts_at"])
        return rows

    def overview(self) -> dict:
        appts = self._today_appointments()
        return {
            "total_today": len(appts),
            "waiting": sum(1 for a in appts if a.status == "booked"),
            "checked_in": sum(1 for a in appts if a.status == "checked_in"),
            "in_treatment": sum(1 for a in appts if a.status == "in_treatment"),
            "completed": sum(1 for a in appts if a.status == "completed"),
            "active": sum(1 for a in appts if a.status in _ACTIVE),
        }
