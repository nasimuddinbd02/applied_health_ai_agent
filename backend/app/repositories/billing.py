"""Billing data access: invoices and their line items."""

from sqlmodel import select

from app.models import Invoice, InvoiceLineItem, utcnow
from app.repositories.base import BaseRepository


class BillingRepository(BaseRepository):
    # ----------------------------------------------------------------- #
    # Invoices
    # ----------------------------------------------------------------- #
    def create_invoice(self, patient_id: int, appointment_id: int | None, status: str = "draft") -> Invoice:
        with self._session() as s:
            invoice = Invoice(patient_id=patient_id, appointment_id=appointment_id, status=status)
            s.add(invoice)
            s.commit()
            s.refresh(invoice)
            return invoice

    def get_invoice(self, invoice_id: int) -> Invoice | None:
        with self._session() as s:
            return s.get(Invoice, invoice_id)

    def get_invoice_by_appointment(self, appointment_id: int) -> Invoice | None:
        with self._session() as s:
            return s.exec(
                select(Invoice).where(Invoice.appointment_id == appointment_id)
            ).first()

    def list_by_patient(self, patient_id: int) -> list[Invoice]:
        with self._session() as s:
            return list(
                s.exec(
                    select(Invoice).where(Invoice.patient_id == patient_id)
                    .order_by(Invoice.created_at.desc())
                ).all()
            )

    def set_status(self, invoice_id: int, status: str, *, mark_paid_now: bool = False) -> Invoice | None:
        with self._session() as s:
            invoice = s.get(Invoice, invoice_id)
            if invoice is None:
                return None
            invoice.status = status
            if mark_paid_now:
                invoice.paid_at = utcnow()
            s.add(invoice)
            s.commit()
            s.refresh(invoice)
            return invoice

    # ----------------------------------------------------------------- #
    # Line items
    # ----------------------------------------------------------------- #
    def add_line_item(self, invoice_id: int, description: str, amount: float, kind: str) -> InvoiceLineItem:
        """Append a line item and roll its amount into the invoice totals."""
        with self._session() as s:
            item = InvoiceLineItem(
                invoice_id=invoice_id, description=description, amount=amount, kind=kind
            )
            s.add(item)
            invoice = s.get(Invoice, invoice_id)
            if invoice is not None:
                invoice.subtotal = round(invoice.subtotal + amount, 2)
                invoice.total = invoice.subtotal
                s.add(invoice)
            s.commit()
            s.refresh(item)
            return item

    def list_items(self, invoice_id: int) -> list[InvoiceLineItem]:
        with self._session() as s:
            return list(
                s.exec(
                    select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice_id)
                    .order_by(InvoiceLineItem.id)
                ).all()
            )
