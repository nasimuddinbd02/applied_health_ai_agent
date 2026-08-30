"""Reception front-desk: today's queue enrichment + counters."""

from datetime import datetime

from app.core.container import container
from app.models import today_iso

reception = container.reception
appt = container.appointments
admin = container.admin


def _book_today():
    """Create a doctor + a slot that starts today, then book it. Returns the
    booked appointment dict and the patient/doctor for assertions."""
    doctor = admin.create_doctor(
        {"name": "ZZZ Reception Doc"}, login_email=f"recdoc.{datetime.now().timestamp()}@t.test",
        login_password="x",
    )["doctor"]
    starts = f"{today_iso()}T08:00:00"
    slot = container.domain_repo.create_slot(doctor.id, starts, 30)
    patient = appt.register_patient({"name": "Queue Patient"})
    booked = appt.book(patient.id, doctor.id, slot.id, "morning visit")
    return booked, patient, doctor


def test_today_queue_includes_todays_booking_with_names():
    booked, patient, doctor = _book_today()
    queue = reception.today_queue()
    row = next((r for r in queue if r["appointment_id"] == booked["appointment_id"]), None)
    assert row is not None, "today's booking should appear in the queue"
    assert row["patient_name"] == patient.name
    assert row["doctor_name"] == doctor.name
    assert row["status"] == "booked"


def test_queue_is_ordered_by_start_time():
    reception.today_queue()  # ensure at least the earlier booking exists
    times = [r["starts_at"] for r in reception.today_queue()]
    assert times == sorted(times)


def test_overview_counts_reflect_status():
    booked, _, _ = _book_today()
    before = reception.overview()
    appt.check_in(booked["appointment_id"])
    after = reception.overview()
    assert after["checked_in"] == before["checked_in"] + 1
    assert after["waiting"] == before["waiting"] - 1
