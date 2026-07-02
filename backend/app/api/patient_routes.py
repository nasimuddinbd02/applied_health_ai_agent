"""Patient controller: self-registration, profile, appointments, treatment history."""

from fastapi import APIRouter, HTTPException

from app.models.schemas import PatientCreate
from app.providers.appointment_provider import AppointmentProvider


class PatientController:
    def __init__(self, appointments: AppointmentProvider) -> None:
        self._appt = appointments
        self.router = APIRouter(prefix="/api/patients", tags=["patients"])
        self._register()

    def _register(self) -> None:
        r = self.router
        r.add_api_route("", self.create_patient, methods=["POST"])
        r.add_api_route("", self.list_patients, methods=["GET"])
        # Registered before "/{patient_id}" so the literal path wins the match.
        r.add_api_route("/lookup", self.lookup, methods=["GET"])
        r.add_api_route("/{patient_id}", self.get_patient, methods=["GET"])
        r.add_api_route("/{patient_id}/appointments", self.appointments, methods=["GET"])
        r.add_api_route("/{patient_id}/treatments", self.treatments, methods=["GET"])

    def create_patient(self, body: PatientCreate):
        return self._appt.register_patient(body.model_dump())

    def list_patients(self):
        return self._appt.list_patients()

    def lookup(self, first_name: str, last_name: str):
        matches = self._appt.find_patients_by_name(first_name, last_name)
        return [
            {"id": p.id, "name": p.name, "date_of_birth": p.date_of_birth, "gender": p.gender}
            for p in matches
        ]

    def get_patient(self, patient_id: int):
        patient = self._appt.get_patient(patient_id)
        if not patient:
            raise HTTPException(404, "Patient not found")
        return patient

    def appointments(self, patient_id: int):
        return self._appt.patient_appointments(patient_id)

    def treatments(self, patient_id: int):
        return self._appt.patient_treatments(patient_id)
