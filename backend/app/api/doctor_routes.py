"""Doctor controller: directory, profile, schedule/availability, appointments."""

from fastapi import APIRouter, HTTPException

from app.providers.appointment_provider import AppointmentProvider


class DoctorController:
    def __init__(self, appointments: AppointmentProvider) -> None:
        self._appt = appointments
        self.router = APIRouter(prefix="/api/doctors", tags=["doctors"])
        self._register()

    def _register(self) -> None:
        r = self.router
        r.add_api_route("", self.list_doctors, methods=["GET"])
        r.add_api_route("/{doctor_id}", self.get_doctor, methods=["GET"])
        r.add_api_route("/{doctor_id}/availability", self.availability, methods=["GET"])
        r.add_api_route("/{doctor_id}/appointments", self.appointments, methods=["GET"])

    def list_doctors(self):
        return self._appt.list_doctors()

    def get_doctor(self, doctor_id: int):
        doctor = self._appt.get_doctor(doctor_id)
        if not doctor:
            raise HTTPException(404, "Doctor not found")
        return doctor

    def availability(self, doctor_id: int):
        if not self._appt.get_doctor(doctor_id):
            raise HTTPException(404, "Doctor not found")
        return self._appt.doctor_availability(doctor_id)

    def appointments(self, doctor_id: int):
        return self._appt.doctor_appointments(doctor_id)
