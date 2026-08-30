"""Pharmacy stock, dispensed prescriptions, and patient refill requests."""

from sqlmodel import Field, SQLModel

from app.models.base import now_iso


class Medicine(SQLModel, table=True):
    """A stock item in the clinic pharmacy."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    dosage_form: str = ""  # tablet | capsule | syrup | injection | …
    unit: str = ""  # e.g. "500mg"
    stock_count: int = 0
    unit_price: float = 0.0


class Prescription(SQLModel, table=True):
    """A medicine prescribed as part of a treatment. Decrements stock on create."""

    id: int | None = Field(default=None, primary_key=True)
    treatment_id: int = Field(foreign_key="treatment.id", index=True)
    medicine_id: int = Field(foreign_key="medicine.id", index=True)
    quantity: int = 1
    frequency: str = ""  # e.g. "twice daily"
    duration_days: int = 0
    dispensed_at: str | None = None
    created_at: str = Field(default_factory=now_iso)


class RefillRequest(SQLModel, table=True):
    """A patient's request to refill a medication, raised via the chat agent.

    Deliberately a staff-reviewed queue rather than an automatic dispense: the
    agent must not make the clinical call on its own.
    """

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    medication: str
    notes: str = ""
    status: str = "pending"  # pending | approved | denied
    created_at: str = Field(default_factory=now_iso)
