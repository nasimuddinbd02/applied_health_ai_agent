"""Billing: auto-draft at checkout, pay, void, and idempotency."""

import uuid

import pytest

from app.container import container
from app.models.entities import today_iso
from app.providers.billing_provider import BillingError

appt = container.appointments
admin = container.admin
billing = container.billing


def _complete_a_visit(fee: float = 120.0):
    """Onboard a doctor with a known fee, open a slot, then run a patient all
    the way through the lifecycle to checkout — which drafts the invoice."""
    doctor = admin.create_doctor(
        {"name": f"ZZZ Bill Doc {uuid.uuid4().hex[:5]}", "consultation_fee": fee},
        login_email=f"bill.{uuid.uuid4().hex[:8]}@t.test", login_password="x",
    )["doctor"]
    slot = container.domain_repo.create_slot(doctor.id, f"{today_iso()}T14:00:00", 30)
    patient = appt.register_patient({"name": "Billing Patient"})
    aid = appt.book(patient.id, doctor.id, slot.id, "visit")["appointment_id"]
    appt.check_in(aid)
    appt.record_treatment(aid, "Checkup", "None", "")
    appt.checkout(aid)
    return aid, patient, fee


def test_checkout_drafts_invoice_with_consultation_fee():
    aid, patient, fee = _complete_a_visit(fee=150.0)
    invoices = billing.list_for_patient(patient.id)
    inv = next((i for i in invoices if i.appointment_id == aid), None)
    assert inv is not None, "checkout should have created an invoice"
    assert inv.total == fee
    assert inv.status == "issued"

    detail = billing.get_with_items(inv.id)
    assert len(detail["items"]) == 1
    assert detail["items"][0].kind == "consultation"
    assert detail["items"][0].amount == fee


def test_invoice_generation_is_idempotent():
    aid, _, _ = _complete_a_visit()
    first = billing.generate_invoice_for_appointment(aid)
    second = billing.generate_invoice_for_appointment(aid)
    assert first.id == second.id


def test_mark_paid_sets_status_and_timestamp():
    aid, patient, _ = _complete_a_visit()
    inv = next(i for i in billing.list_for_patient(patient.id) if i.appointment_id == aid)
    paid = billing.mark_paid(inv.id)
    assert paid.status == "paid"
    assert paid.paid_at is not None


def test_void_then_pay_is_rejected():
    aid, patient, _ = _complete_a_visit()
    inv = next(i for i in billing.list_for_patient(patient.id) if i.appointment_id == aid)
    billing.void(inv.id)
    with pytest.raises(BillingError):
        billing.mark_paid(inv.id)


def test_paid_invoice_cannot_be_voided():
    aid, patient, _ = _complete_a_visit()
    inv = next(i for i in billing.list_for_patient(patient.id) if i.appointment_id == aid)
    billing.mark_paid(inv.id)
    with pytest.raises(BillingError):
        billing.void(inv.id)
