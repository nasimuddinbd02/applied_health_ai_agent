"""Appointment lifecycle: register, book (with double-book guard), check-in,
treatment, checkout, and treatment history."""

import pytest

from app.container import container
from app.providers.appointment_provider import AppointmentError

appt = container.appointments


def _new_patient():
    return appt.register_patient({"name": "Test Patient", "gender": "female", "blood_group": "O+"})


def _first_open_slot():
    doctor = appt.list_doctors()[0]
    slots = appt.doctor_availability(doctor.id)
    return doctor, slots[0]


def test_register_patient_creates_profile():
    p = _new_patient()
    assert p.id is not None
    assert appt.get_patient(p.id).name == "Test Patient"


def test_full_lifecycle_book_checkin_treat_checkout():
    patient = _new_patient()
    doctor, slot = _first_open_slot()

    booked = appt.book(patient.id, doctor.id, slot["slot_id"], "annual check-up")
    aid = booked["appointment_id"]
    assert booked["status"] == "booked"

    assert appt.check_in(aid).status == "checked_in"
    treatment = appt.record_treatment(aid, "Healthy", "None", "All good")
    assert treatment.id is not None
    assert appt.get_appointment(aid).status == "in_treatment"
    assert appt.checkout(aid).status == "completed"

    # treatment history reflects it
    history = appt.patient_treatments(patient.id)
    assert any(t.id == treatment.id for t in history)


def test_no_double_booking():
    patient = _new_patient()
    doctor, slot = _first_open_slot()
    appt.book(patient.id, doctor.id, slot["slot_id"], "first")
    with pytest.raises(AppointmentError):
        appt.book(patient.id, doctor.id, slot["slot_id"], "second")


def test_invalid_transition_rejected():
    patient = _new_patient()
    doctor, slot = _first_open_slot()
    aid = appt.book(patient.id, doctor.id, slot["slot_id"], "x")["appointment_id"]
    # cannot record treatment before check-in
    with pytest.raises(AppointmentError):
        appt.record_treatment(aid, "dx", "rx", "n")


def test_cancel_frees_slot():
    patient = _new_patient()
    doctor, slot = _first_open_slot()
    aid = appt.book(patient.id, doctor.id, slot["slot_id"], "x")["appointment_id"]
    assert appt.cancel(aid).status == "cancelled"
    # slot is open again -> re-bookable
    rebook = appt.book(patient.id, doctor.id, slot["slot_id"], "again")
    assert rebook["status"] == "booked"
