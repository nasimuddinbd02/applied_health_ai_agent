"""The MCP appointment tools (what the LLM agent calls) — exercised directly,
without the LLM, so booking logic + guarantees are covered deterministically."""

import pytest

from app.core.container import container
from app.mcp import tools

appt = container.appointments


def _patient_id():
    return appt.register_patient({"name": "Tool Tester"}).id


def test_get_doctors_lists_specialties():
    docs = tools.get_doctors()
    assert docs and all("specialty" in d for d in docs)


def test_find_doctors_by_specialty():
    res = tools.find_doctors_by_specialty("cardiology")
    assert res and "cardio" in res[0]["specialty"].lower()


def test_get_availability_returns_open_slots():
    did = tools.get_doctors()[0]["doctor_id"]
    slots = tools.get_availability(did)
    assert slots and "slot_id" in slots[0]


def test_book_then_double_book_is_rejected():
    pid = _patient_id()
    did = tools.get_doctors()[0]["doctor_id"]
    slot = tools.get_availability(did)[0]["slot_id"]
    ok = tools.book_appointment(pid, did, slot, "checkup")
    assert "appointment_id" in ok
    dup = tools.book_appointment(pid, did, slot, "again")
    assert "error" in dup


def test_get_patient_tool():
    pid = _patient_id()
    assert tools.get_patient(pid)["patient_id"] == pid
    assert "error" in tools.get_patient(999999)


@pytest.mark.parametrize("specialty", ["dermatology", "neurology", "orthopedics"])
def test_each_specialty_has_a_doctor(specialty):
    assert tools.find_doctors_by_specialty(specialty)
