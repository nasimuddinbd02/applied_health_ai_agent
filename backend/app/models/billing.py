"""Invoices raised at checkout."""

from sqlmodel import Field, SQLModel

from app.models.base import now_iso


class Invoice(SQLModel, table=True):
    """A bill for a visit. Auto-drafted at checkout from the consultation fee."""

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    appointment_id: int | None = Field(default=None, foreign_key="appointment.id", index=True)
    status: str = "draft"  # draft | issued | paid | void
    subtotal: float = 0.0
    total: float = 0.0
    created_at: str = Field(default_factory=now_iso)
    paid_at: str | None = None


class InvoiceLineItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    description: str = ""
    amount: float = 0.0
    kind: str = "consultation"  # consultation | medicine | other
