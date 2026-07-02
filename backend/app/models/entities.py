"""SQLModel tables for the hospital domain.

Integer PKs, ISO datetime strings. Kept deliberately flat and readable.
"""

from datetime import UTC, date, datetime

from sqlmodel import Field, SQLModel


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# --------------------------------------------------------------------------- #
# People
# --------------------------------------------------------------------------- #
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
    created_at: str = Field(default_factory=_now_iso)


class Doctor(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    specialty: str = ""
    email: str = ""
    phone: str = ""
    room: str = ""
    bio: str = ""
    consultation_fee: float = 0.0


# --------------------------------------------------------------------------- #
# Scheduling
# --------------------------------------------------------------------------- #
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
    created_at: str = Field(default_factory=_now_iso)


# --------------------------------------------------------------------------- #
# Clinical
# --------------------------------------------------------------------------- #
class Treatment(SQLModel, table=True):
    """A record of a doctor's treatment — forms the treatment history."""

    id: int | None = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointment.id", index=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    doctor_id: int = Field(foreign_key="doctor.id", index=True)
    diagnosis: str = ""
    prescription: str = ""
    notes: str = ""
    created_at: str = Field(default_factory=_now_iso)


# --------------------------------------------------------------------------- #
# Billing
# --------------------------------------------------------------------------- #
class Invoice(SQLModel, table=True):
    """A bill for a visit. Auto-drafted at checkout from the consultation fee."""

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    appointment_id: int | None = Field(default=None, foreign_key="appointment.id", index=True)
    status: str = "draft"  # draft | issued | paid | void
    subtotal: float = 0.0
    total: float = 0.0
    created_at: str = Field(default_factory=_now_iso)
    paid_at: str | None = None


class InvoiceLineItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    description: str = ""
    amount: float = 0.0
    kind: str = "consultation"  # consultation | medicine | other


# --------------------------------------------------------------------------- #
# Pharmacy
# --------------------------------------------------------------------------- #
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
    created_at: str = Field(default_factory=_now_iso)


# --------------------------------------------------------------------------- #
# Refill requests (lightweight — a staff-reviewed queue raised via the agent)
# --------------------------------------------------------------------------- #
class RefillRequest(SQLModel, table=True):
    """A patient's request to refill a medication, raised via the chat agent."""

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    medication: str
    notes: str = ""
    status: str = "pending"  # pending | approved | denied
    created_at: str = Field(default_factory=_now_iso)


# --------------------------------------------------------------------------- #
# Appointment-agent chat
# --------------------------------------------------------------------------- #
class ChatMessage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    thread_id: str = Field(index=True)
    patient_id: int | None = Field(default=None, foreign_key="patient.id")
    role: str = "patient"  # patient | agent
    content: str = ""
    created_at: str = Field(default_factory=_now_iso)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class User(SQLModel, table=True):
    """A login identity. Roles: admin | doctor | receptionist | patient."""

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    role: str = "patient"
    patient_id: int | None = Field(default=None, foreign_key="patient.id")
    doctor_id: int | None = Field(default=None, foreign_key="doctor.id")
    is_active: bool = True
    created_at: str = Field(default_factory=_now_iso)


# --------------------------------------------------------------------------- #
# Ops
# --------------------------------------------------------------------------- #
class AuditEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: str = Field(default_factory=_now_iso)
    feature: str = ""
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    est_cost_usd: float = 0.0
    outcome: str = ""
    summary: str = ""  # PII-redacted


def utcnow() -> str:
    return _now_iso()


def today_iso() -> str:
    return date.today().isoformat()
