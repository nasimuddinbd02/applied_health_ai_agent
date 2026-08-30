"""Booking and treatment DTOs."""

from pydantic import BaseModel


class AppointmentRequest(BaseModel):
    patient_id: int
    doctor_id: int
    slot_id: int
    reason: str = ""


class PrescriptionItem(BaseModel):
    medicine_id: int
    quantity: int = 1
    frequency: str = ""
    duration_days: int = 0


class TreatmentCreate(BaseModel):
    diagnosis: str = ""
    prescription: str = ""
    notes: str = ""
    prescriptions: list[PrescriptionItem] = []
