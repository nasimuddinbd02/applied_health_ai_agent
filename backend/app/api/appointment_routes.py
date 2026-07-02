"""Appointment controller: book + lifecycle (check-in, treatment, checkout, cancel).

Domain errors (AppointmentError / PharmacyError) propagate to the global
handlers registered in ``app.lib.error_handlers`` and become 400 responses.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.lib.authz import require_role
from app.models.schemas import AppointmentRequest, TreatmentCreate
from app.providers.appointment_provider import AppointmentProvider

_STAFF = Depends(require_role("doctor", "receptionist", "admin"))


class AppointmentController:
    def __init__(self, appointments: AppointmentProvider, billing=None, pharmacy=None) -> None:
        self._appt = appointments
        self._billing = billing
        self._pharmacy = pharmacy
        self.router = APIRouter(prefix="/api/appointments", tags=["appointments"])
        self._register()

    def _register(self) -> None:
        r = self.router
        r.add_api_route("", self.book, methods=["POST"])
        r.add_api_route("/{appointment_id}", self.get, methods=["GET"])
        r.add_api_route(
            "/{appointment_id}/check-in", self.check_in, methods=["POST"],
            dependencies=[_STAFF],
        )
        r.add_api_route(
            "/{appointment_id}/treatment", self.treatment, methods=["POST"],
            dependencies=[_STAFF],
        )
        r.add_api_route(
            "/{appointment_id}/checkout", self.checkout, methods=["POST"],
            dependencies=[_STAFF],
        )
        r.add_api_route("/{appointment_id}/cancel", self.cancel, methods=["POST"])

    def book(self, body: AppointmentRequest):
        return self._appt.book(body.patient_id, body.doctor_id, body.slot_id, body.reason)

    def get(self, appointment_id: int):
        appt = self._appt.get_appointment(appointment_id)
        if not appt:
            raise HTTPException(404, "Appointment not found")
        invoice = self._billing.invoice_for_appointment(appointment_id) if self._billing else None
        treatment = self._appt.treatment_for_appointment(appointment_id)
        prescriptions = (
            self._pharmacy.prescriptions_for_treatment(treatment.id)
            if treatment and self._pharmacy else []
        )
        return {
            "appointment": appt,
            "patient": self._appt.get_patient(appt.patient_id),
            "doctor": self._appt.get_doctor(appt.doctor_id),
            "treatment": treatment,
            "invoice": invoice,
            "prescriptions": prescriptions,
        }

    def check_in(self, appointment_id: int):
        return self._appt.check_in(appointment_id)

    def treatment(self, appointment_id: int, body: TreatmentCreate):
        treatment = self._appt.record_treatment(
            appointment_id, body.diagnosis, body.prescription, body.notes
        )
        # Dispense any structured prescriptions in the same step (decrements
        # pharmacy stock). Kept in the controller so the doctor's workflow
        # stays a single request.
        if self._pharmacy and body.prescriptions:
            self._pharmacy.prescribe(
                treatment.id, [p.model_dump() for p in body.prescriptions]
            )
        return treatment

    def checkout(self, appointment_id: int):
        return self._appt.checkout(appointment_id)

    def cancel(self, appointment_id: int):
        return self._appt.cancel(appointment_id)
