"""Pharmacy: stock intake, stock-aware prescribing, and prescription listing."""

import uuid

import pytest

from app.core.container import container
from app.models import today_iso
from app.services.pharmacy import PharmacyError

pharmacy = container.pharmacy
appt = container.appointments
admin = container.admin


def _a_treatment_id() -> int:
    """Run a patient to the point a treatment exists, and return its id."""
    doctor = admin.create_doctor(
        {"name": f"ZZZ Rx Doc {uuid.uuid4().hex[:5]}"},
        login_email=f"rx.{uuid.uuid4().hex[:8]}@t.test", login_password="x",
    )["doctor"]
    slot = container.domain_repo.create_slot(doctor.id, f"{today_iso()}T11:00:00", 30)
    patient = appt.register_patient({"name": "Rx Patient"})
    aid = appt.book(patient.id, doctor.id, slot.id, "visit")["appointment_id"]
    appt.check_in(aid)
    return appt.record_treatment(aid, "Dx", "", "").id


def _add_medicine(stock: int) -> int:
    return pharmacy.add_medicine(f"ZZZ Med {uuid.uuid4().hex[:5]}", "tablet", "5mg", stock, 1.0)["id"]


def test_prescribe_decrements_stock_and_records_prescription():
    med_id = _add_medicine(stock=10)
    tid = _a_treatment_id()

    pharmacy.prescribe(tid, [{"medicine_id": med_id, "quantity": 3, "frequency": "twice daily", "duration_days": 5}])

    med = next(m for m in pharmacy.list_medicines() if m["id"] == med_id)
    assert med["stock_count"] == 7

    rxs = pharmacy.prescriptions_for_treatment(tid)
    assert len(rxs) == 1
    assert rxs[0]["quantity"] == 3
    assert rxs[0]["frequency"] == "twice daily"


def test_insufficient_stock_is_rejected_and_leaves_stock_untouched():
    med_id = _add_medicine(stock=2)
    tid = _a_treatment_id()

    with pytest.raises(PharmacyError):
        pharmacy.prescribe(tid, [{"medicine_id": med_id, "quantity": 5}])

    med = next(m for m in pharmacy.list_medicines() if m["id"] == med_id)
    assert med["stock_count"] == 2  # unchanged
    assert pharmacy.prescriptions_for_treatment(tid) == []


def test_multi_item_prescription_is_all_or_nothing():
    ok_id = _add_medicine(stock=10)
    short_id = _add_medicine(stock=1)
    tid = _a_treatment_id()

    # second item is short — the whole prescription must be rejected
    with pytest.raises(PharmacyError):
        pharmacy.prescribe(tid, [
            {"medicine_id": ok_id, "quantity": 2},
            {"medicine_id": short_id, "quantity": 5},
        ])

    ok = next(m for m in pharmacy.list_medicines() if m["id"] == ok_id)
    assert ok["stock_count"] == 10  # the in-stock item was NOT decremented
    assert pharmacy.prescriptions_for_treatment(tid) == []


def test_restock_and_low_stock():
    med_id = _add_medicine(stock=3)
    low = pharmacy.low_stock(threshold=5)
    assert any(m["id"] == med_id for m in low)

    pharmacy.restock(med_id, 20)
    med = next(m for m in pharmacy.list_medicines() if m["id"] == med_id)
    assert med["stock_count"] == 23
