"""Login identities."""

from sqlmodel import Field, SQLModel

from app.models.base import now_iso


class User(SQLModel, table=True):
    """A login identity. Roles: admin | doctor | receptionist | patient."""

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    role: str = "patient"
    patient_id: int | None = Field(default=None, foreign_key="patient.id")
    doctor_id: int | None = Field(default=None, foreign_key="doctor.id")
    is_active: bool = True
    created_at: str = Field(default_factory=now_iso)
