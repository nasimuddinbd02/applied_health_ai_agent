"""Appointment tool implementations -> AppointmentService (from the container).

Thin pass-through so the MCP server's @mcp.tool functions stay declarative and
the real logic / guarantees live in the service.
"""

from app.core.container import container

_svc = container.appointments


def get_doctors() -> list[dict]:
    return [
        {"doctor_id": d.id, "name": d.name, "specialty": d.specialty, "room": d.room}
        for d in _svc.list_doctors()
    ]


def find_doctors_by_specialty(specialty: str) -> list[dict]:
    return [
        {"doctor_id": d.id, "name": d.name, "specialty": d.specialty}
        for d in _svc.find_doctors_by_specialty(specialty)
    ]


def get_availability(doctor_id: int) -> list[dict]:
    return _svc.doctor_availability(doctor_id)


def book_appointment(patient_id: int, doctor_id: int, slot_id: int, reason: str = "") -> dict:
    try:
        return _svc.book(patient_id, doctor_id, slot_id, reason)
    except Exception as err:  # surfaced to the agent as a tool error
        return {"error": str(err)}


def get_patient(patient_id: int) -> dict:
    p = _svc.get_patient(patient_id)
    if not p:
        return {"error": f"Patient {patient_id} not found."}
    return {"patient_id": p.id, "name": p.name, "gender": p.gender, "blood_group": p.blood_group}


def find_patient_by_name(first_name: str, last_name: str) -> list[dict]:
    """Look up an existing patient by first + last name (case-insensitive)."""
    return [
        {"patient_id": p.id, "name": p.name, "date_of_birth": p.date_of_birth, "gender": p.gender}
        for p in _svc.find_patients_by_name(first_name, last_name)
    ]


def register_patient(
    name: str, email: str = "", phone: str = "", gender: str = "",
    date_of_birth: str | None = None, address: str = "", blood_group: str = "",
) -> dict:
    """Create a brand-new patient profile. Only call this after confirming the
    patient is not already registered (via find_patient_by_name)."""
    try:
        p = _svc.register_patient({
            "name": name, "email": email, "phone": phone, "gender": gender,
            "date_of_birth": date_of_birth, "address": address, "blood_group": blood_group,
        })
        return {"patient_id": p.id, "name": p.name}
    except Exception as err:
        return {"error": str(err)}


def request_refill(patient_id: int, medication: str, notes: str = "") -> dict:
    """Submit a medication refill request for clinic staff to review."""
    try:
        r = _svc.request_refill(patient_id, medication, notes)
        return {
            "refill_request_id": r.id, "patient_id": r.patient_id,
            "medication": r.medication, "status": r.status,
        }
    except Exception as err:
        return {"error": str(err)}
