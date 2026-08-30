"""Wire protocol + server-side reading of tool results."""

import json

import pytest
from pydantic import ValidationError

from app.realtime.protocol import TOOL_STATUS, ClientMessage, ServerEvents
from app.realtime.tool_results import ToolResultReader


# --------------------------------------------------------------------------- #
# Client frames
# --------------------------------------------------------------------------- #
def test_user_message_gets_an_automatic_message_id():
    frame = ClientMessage.model_validate_json('{"type":"user_message","message":"hi"}')
    assert frame.message_id.startswith("msg-")


def test_unknown_frame_type_is_rejected():
    with pytest.raises(ValidationError):
        ClientMessage.model_validate_json('{"type":"drop_database"}')


def test_client_cannot_smuggle_extra_fields():
    frame = ClientMessage.model_validate_json(
        '{"type":"user_message","message":"hi","patient_id":7,"role":"admin"}'
    )
    assert not hasattr(frame, "patient_id")


# --------------------------------------------------------------------------- #
# Server frames
# --------------------------------------------------------------------------- #
def test_agent_status_carries_the_correlation_id():
    event = ServerEvents.agent_status(
        status="checking_availability", conversation_id="conv-1", correlation_id="corr-1"
    )
    assert event == {
        "type": "agent_status", "conversation_id": "conv-1",
        "correlation_id": "corr-1", "status": "checking_availability",
    }


def test_every_mapped_tool_has_a_customer_facing_status():
    assert TOOL_STATUS["get_availability"] == "checking_availability"
    assert all(status and " " not in status for status in TOOL_STATUS.values())


# --------------------------------------------------------------------------- #
# Reading tool output server-side
# --------------------------------------------------------------------------- #
@pytest.fixture
def reader():
    return ToolResultReader()


def test_identity_from_a_registration(reader):
    results = [{"tool": "register_patient", "content": '{"patient_id": 42, "name": "Ada"}'}]
    assert reader.identity(results) == {"patient_id": 42, "name": "Ada"}


def test_identity_from_a_unique_name_match(reader):
    results = [{"tool": "find_patient_by_name",
                "content": json.dumps([{"patient_id": 7, "name": "Olivia Bennett"}])}]
    assert reader.identity(results)["patient_id"] == 7


def test_ambiguous_name_match_is_not_an_identification(reader):
    """Two people share a name — the agent must disambiguate before we bind."""
    results = [{"tool": "find_patient_by_name", "content": json.dumps([
        {"patient_id": 7, "name": "John Smith"},
        {"patient_id": 9, "name": "John Smith"},
    ])}]
    assert reader.identity(results) is None


def test_identity_ignores_unrelated_tools(reader):
    results = [{"tool": "get_doctors", "content": '[{"patient_id": 3}]'}]
    assert reader.identity(results) is None


def test_identity_survives_double_encoded_mcp_output(reader):
    inner = json.dumps({"patient_id": 11, "name": "Ravi"})
    results = [{"tool": "get_patient", "content": json.dumps(inner)}]
    assert reader.identity(results)["patient_id"] == 11


def test_appointment_options_are_built_from_open_slots(reader):
    results = [{"tool": "get_availability", "content": json.dumps([
        {"slot_id": 1, "doctor_id": 2, "starts_at": "2026-09-14T14:30:00", "duration_min": 30},
        {"slot_id": 2, "doctor_id": 2, "starts_at": "2026-09-14T16:00:00", "duration_min": 30},
    ])}]
    options = reader.appointment_options(results)
    assert [o["id"] for o in options] == ["slot-1", "slot-2"]
    assert options[0]["start"] == "2026-09-14T14:30:00"


def test_appointment_options_are_capped(reader):
    slots = [{"slot_id": i, "starts_at": f"2026-09-14T{i:02d}:00:00"} for i in range(1, 20)]
    assert len(reader.appointment_options([
        {"tool": "get_availability", "content": json.dumps(slots)}
    ])) == 6


def test_booked_appointment_is_detected(reader):
    results = [{"tool": "book_appointment", "content": '{"appointment_id": 5}'}]
    assert reader.booked_appointment(results)["appointment_id"] == 5
