"""Patients and doctors."""

from sqlmodel import Field, SQLModel

from app.models.base import now_iso


class Patient(SQLModel, table=True):
    """A patient who can self-register and book appointments."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = ""
    phone: str = ""
    gender: str = ""  # male | female | other
    date_of_birth: str | None = None  # ISO date
    address: str = ""
    blood_group: str = ""
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)


class Doctor(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    specialty: str = ""
    email: str = ""
    phone: str = ""
    room: str = ""
    bio: str = ""
    consultation_fee: float = 0.0
