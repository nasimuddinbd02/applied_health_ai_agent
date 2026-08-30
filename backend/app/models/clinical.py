"""Clinical records produced during a visit."""

from sqlmodel import Field, SQLModel

from app.models.base import now_iso


class Treatment(SQLModel, table=True):
    """A record of a doctor's treatment — forms the treatment history."""

    id: int | None = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointment.id", index=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    doctor_id: int = Field(foreign_key="doctor.id", index=True)
    diagnosis: str = ""
    prescription: str = ""
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)
