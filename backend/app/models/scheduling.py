"""Bookable slots and the appointments made against them."""

from sqlmodel import Field, SQLModel

from app.models.base import now_iso


class AvailabilitySlot(SQLModel, table=True):
    """A bookable slot in a doctor's schedule."""

    id: int | None = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctor.id", index=True)
    starts_at: str  # ISO datetime
    duration_min: int = 30
    is_booked: bool = False


class Appointment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    doctor_id: int = Field(foreign_key="doctor.id", index=True)
    slot_id: int | None = Field(default=None, foreign_key="availabilityslot.id")
    starts_at: str  # ISO datetime
    duration_min: int = 30
    reason: str = ""
    # booked -> checked_in -> in_treatment -> completed ; or cancelled
    status: str = "booked"
    created_at: str = Field(default_factory=now_iso)
