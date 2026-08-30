"""Admin module: doctor onboarding (with login), schedule generation, slot removal."""

import uuid

import pytest

from app.core.container import container
from app.services.admin import AdminError

admin = container.admin
auth = container.auth
appt = container.appointments


def _unique_email() -> str:
    return f"dr.{uuid.uuid4().hex[:8]}@clinic.test"


# Test doctors are named with a "ZZZ" prefix so they sort AFTER every seeded
# doctor — sibling tests grab ``list_doctors()[0]`` and assume it's a seeded
# doctor with availability, so newly-created doctors must not jump to the front.
def _doc_name(label: str) -> str:
    return f"ZZZ {label} {uuid.uuid4().hex[:6]}"


def test_create_doctor_provisions_a_working_login():
    email = _unique_email()
    result = admin.create_doctor(
        {"name": _doc_name("New Hire"), "specialty": "Cardiology", "consultation_fee": 100.0},
        login_email=email, login_password="temp123",
    )
    doctor = result["doctor"]
    assert doctor.id is not None
    # the doctor now shows up in the public directory
    assert any(d.id == doctor.id for d in appt.list_doctors())
    # and the login works, linked to this doctor
    token, user = auth.login(email, "temp123")
    assert user.role == "doctor"
    assert user.doctor_id == doctor.id


def test_create_doctor_rejects_taken_email():
    email = _unique_email()
    admin.create_doctor({"name": _doc_name("A")}, login_email=email, login_password="x")
    with pytest.raises(AdminError):
        admin.create_doctor({"name": _doc_name("B")}, login_email=email, login_password="y")


def test_generate_schedule_creates_expected_slots_and_is_idempotent():
    doctor = admin.create_doctor(
        {"name": _doc_name("Schedule")}, login_email=_unique_email(), login_password="x"
    )["doctor"]

    # Mon+Tue+Wed, 09:00–12:00, 30-min slots, 1 week → 6 slots/day * 3 days = 18
    template = dict(
        weekdays=[0, 1, 2], start_time="09:00", end_time="12:00",
        slot_minutes=30, weeks=1, start_date="2026-07-06",  # a Monday
    )
    first = admin.generate_schedule(doctor.id, **template)
    assert first["created"] == 18
    assert first["skipped"] == 0

    # re-running the same template creates nothing new
    second = admin.generate_schedule(doctor.id, **template)
    assert second["created"] == 0
    assert second["skipped"] == 18

    slots = admin.list_slots(doctor.id)
    assert len(slots) == 18
    assert all(not s["is_booked"] for s in slots)


def test_generate_schedule_validates_input():
    doctor = admin.create_doctor(
        {"name": _doc_name("Bad Input")}, login_email=_unique_email(), login_password="x"
    )["doctor"]
    with pytest.raises(AdminError):  # end before start
        admin.generate_schedule(
            doctor.id, weekdays=[0], start_time="12:00", end_time="09:00",
            slot_minutes=30, weeks=1,
        )
    with pytest.raises(AdminError):  # no weekdays
        admin.generate_schedule(
            doctor.id, weekdays=[], start_time="09:00", end_time="12:00",
            slot_minutes=30, weeks=1,
        )


def test_delete_slot_refuses_booked_slot():
    doctor = admin.create_doctor(
        {"name": _doc_name("Booked")}, login_email=_unique_email(), login_password="x"
    )["doctor"]
    admin.generate_schedule(
        doctor.id, weekdays=[0, 1, 2, 3, 4], start_time="09:00", end_time="10:00",
        slot_minutes=30, weeks=2,
    )
    slots = admin.list_slots(doctor.id)
    assert slots, "expected generated slots"

    # an open slot can be removed
    admin.remove_slot(slots[0]["slot_id"])

    # book the next one, then removal must be refused
    patient = appt.register_patient({"name": "Booker"})
    booked = appt.book(patient.id, doctor.id, slots[1]["slot_id"], "visit")
    assert booked["status"] == "booked"
    with pytest.raises(AdminError):
        admin.remove_slot(slots[1]["slot_id"])


def test_update_doctor_changes_profile():
    original_name = _doc_name("Old")
    doctor = admin.create_doctor(
        {"name": original_name, "room": "Room 1"}, login_email=_unique_email(), login_password="x"
    )["doctor"]
    updated = admin.update_doctor(doctor.id, {"room": "Room 2", "consultation_fee": 150.0})
    assert updated.room == "Room 2"
    assert updated.consultation_fee == 150.0
    # name left untouched because it wasn't in the change set
    assert updated.name == original_name
