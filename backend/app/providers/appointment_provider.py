"""Appointment business logic: registration, scheduling, lifecycle, treatments.

Holds the business rules (status transitions, slot selection); persistence and
the no-double-booking guarantee are delegated to the repository.

Lifecycle:  booked -> checked_in -> in_treatment -> completed   (or cancelled)
"""

from app.dbacces.domain_repository import DomainRepository
from app.models.entities import today_iso


class AppointmentError(Exception):
    """Raised on an invalid lifecycle transition or bad booking request."""


class AppointmentProvider:
    def __init__(self, domain_repo: DomainRepository, billing=None) -> None:
        self._domain = domain_repo
        # Optional BillingProvider — set by the container so checkout can auto
        # draft an invoice. Kept optional so tests/tools can build the provider
        # standalone without pulling in billing.
        self._billing = billing

    # ----------------------------------------------------------------- #
    # Patients
    # ----------------------------------------------------------------- #
    def register_patient(self, data: dict):
        if not data.get("name"):
            raise AppointmentError("Patient name is required.")
        return self._domain.create_patient(**data)

    def list_patients(self):
        return self._domain.list_patients()

    def get_patient(self, patient_id: int):
        return self._domain.get_patient(patient_id)

    def find_patients_by_name(self, first_name: str, last_name: str):
        return self._domain.find_patients_by_name(first_name, last_name)

    # ----------------------------------------------------------------- #
    # Refill requests (used by the chat agent)
    # ----------------------------------------------------------------- #
    def request_refill(self, patient_id: int, medication: str, notes: str = ""):
        if not self._domain.get_patient(patient_id):
            raise AppointmentError(f"Patient {patient_id} does not exist.")
        if not medication.strip():
            raise AppointmentError("Medication name is required.")
        return self._domain.create_refill_request(patient_id, medication.strip(), notes)

    def list_refill_requests(self):
        return self._domain.list_refill_requests()

    # ----------------------------------------------------------------- #
    # Doctors & schedule
    # ----------------------------------------------------------------- #
    def list_doctors(self):
        return self._domain.list_doctors()

    def get_doctor(self, doctor_id: int):
        return self._domain.get_doctor(doctor_id)

    def doctor_availability(self, doctor_id: int, after: str | None = None) -> list[dict]:
        slots = self._domain.get_open_slots(doctor_id, after or today_iso())
        return [
            {"slot_id": sl.id, "doctor_id": sl.doctor_id, "starts_at": sl.starts_at,
             "duration_min": sl.duration_min}
            for sl in slots
        ]

    # ----------------------------------------------------------------- #
    # Booking + lifecycle
    # ----------------------------------------------------------------- #
    def book(self, patient_id: int, doctor_id: int, slot_id: int, reason: str = "") -> dict:
        result = self._domain.book_appointment(patient_id, doctor_id, slot_id, reason)
        if "error" in result:
            raise AppointmentError(result["error"])
        return result

    def _require(self, appointment_id: int, expected: str):
        appt = self._domain.get_appointment(appointment_id)
        if appt is None:
            raise AppointmentError("Appointment not found.")
        if appt.status != expected:
            raise AppointmentError(
                f"Appointment is '{appt.status}', expected '{expected}'."
            )
        return appt

    def check_in(self, appointment_id: int):
        self._require(appointment_id, "booked")
        return self._domain.set_appointment_status(appointment_id, "checked_in")

    def record_treatment(self, appointment_id: int, diagnosis: str, prescription: str, notes: str):
        appt = self._require(appointment_id, "checked_in")
        treatment = self._domain.add_treatment(
            appointment_id, appt.patient_id, appt.doctor_id, diagnosis, prescription, notes
        )
        self._domain.set_appointment_status(appointment_id, "in_treatment")
        return treatment

    def checkout(self, appointment_id: int):
        self._require(appointment_id, "in_treatment")
        appt = self._domain.set_appointment_status(appointment_id, "completed")
        if self._billing is not None:
            self._billing.generate_invoice_for_appointment(appointment_id)
        return appt

    def cancel(self, appointment_id: int):
        appt = self._domain.get_appointment(appointment_id)
        if appt is None:
            raise AppointmentError("Appointment not found.")
        if appt.status in ("completed", "cancelled"):
            raise AppointmentError(f"Cannot cancel a '{appt.status}' appointment.")
        return self._domain.set_appointment_status(appointment_id, "cancelled", free_slot=True)

    # ----------------------------------------------------------------- #
    # Reads / history
    # ----------------------------------------------------------------- #
    def get_appointment(self, appointment_id: int):
        return self._domain.get_appointment(appointment_id)

    def patient_appointments(self, patient_id: int):
        return self._domain.list_appointments_by_patient(patient_id)

    def doctor_appointments(self, doctor_id: int):
        return self._domain.list_appointments_by_doctor(doctor_id)

    def patient_treatments(self, patient_id: int):
        return self._domain.list_treatments_by_patient(patient_id)

    def treatment_for_appointment(self, appointment_id: int):
        return self._domain.get_treatment_by_appointment(appointment_id)

    # ----------------------------------------------------------------- #
    # Helpers used by the appointment agent
    # ----------------------------------------------------------------- #
    def find_doctors_by_specialty(self, specialty: str):
        return self._domain.find_doctors_by_specialty(specialty)

    def log_chat(self, thread_id: str, patient_id: int | None, role: str, content: str):
        return self._domain.add_chat_message(thread_id, patient_id, role, content)

    def chat_history(self, thread_id: str):
        return self._domain.get_chat_messages(thread_id)
