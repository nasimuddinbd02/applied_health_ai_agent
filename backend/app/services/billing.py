"""Billing business logic: draft invoices at checkout, collect payment, void.

Invoices are auto-drafted when an appointment is checked out — the doctor's
``consultation_fee`` becomes the first line item — and can then be marked paid
or voided by front-desk / admin staff.
"""

from app.repositories.billing import BillingRepository
from app.repositories.domain import DomainRepository


class BillingError(Exception):
    """Raised on an invalid billing request (unknown invoice, bad transition)."""


class BillingService:
    def __init__(self, domain_repo: DomainRepository, billing_repo: BillingRepository) -> None:
        self._domain = domain_repo
        self._billing = billing_repo

    # ----------------------------------------------------------------- #
    # Creation (called from the appointment checkout hook)
    # ----------------------------------------------------------------- #
    def generate_invoice_for_appointment(self, appointment_id: int):
        """Draft an invoice for a completed visit. Idempotent — returns the
        existing invoice if one was already created for this appointment."""
        existing = self._billing.get_invoice_by_appointment(appointment_id)
        if existing is not None:
            return existing

        appt = self._domain.get_appointment(appointment_id)
        if appt is None:
            raise BillingError(f"Appointment {appointment_id} not found.")
        doctor = self._domain.get_doctor(appt.doctor_id)
        fee = float(doctor.consultation_fee) if doctor else 0.0

        invoice = self._billing.create_invoice(appt.patient_id, appointment_id, status="issued")
        label = f"Consultation — {doctor.name}" if doctor else "Consultation"
        self._billing.add_line_item(invoice.id, label, fee, kind="consultation")
        return self._billing.get_invoice(invoice.id)

    # ----------------------------------------------------------------- #
    # Payment lifecycle
    # ----------------------------------------------------------------- #
    def mark_paid(self, invoice_id: int):
        invoice = self._billing.get_invoice(invoice_id)
        if invoice is None:
            raise BillingError("Invoice not found.")
        if invoice.status == "void":
            raise BillingError("A voided invoice cannot be paid.")
        if invoice.status == "paid":
            return invoice
        return self._billing.set_status(invoice_id, "paid", mark_paid_now=True)

    def void(self, invoice_id: int):
        invoice = self._billing.get_invoice(invoice_id)
        if invoice is None:
            raise BillingError("Invoice not found.")
        if invoice.status == "paid":
            raise BillingError("A paid invoice cannot be voided.")
        return self._billing.set_status(invoice_id, "void")

    # ----------------------------------------------------------------- #
    # Reads
    # ----------------------------------------------------------------- #
    def get_with_items(self, invoice_id: int) -> dict:
        invoice = self._billing.get_invoice(invoice_id)
        if invoice is None:
            raise BillingError("Invoice not found.")
        return {"invoice": invoice, "items": self._billing.list_items(invoice_id)}

    def list_for_patient(self, patient_id: int) -> list:
        return self._billing.list_by_patient(patient_id)

    def invoice_for_appointment(self, appointment_id: int):
        return self._billing.get_invoice_by_appointment(appointment_id)
