"""FastMCP MCP server exposing the hospital appointment tools.

Runs as its own process (``make run-mcp``) and shares the SQLite DB with the
API. The LangGraph appointment agent loads these tools via
``langchain-mcp-adapters``; it never imports the handlers directly.
"""

from fastmcp import FastMCP

from app.core.config import settings
from app.db.session import init_db
from app.mcp import tools

mcp = FastMCP("hospital-tools")


@mcp.tool()
def get_doctors() -> list[dict]:
    """List all doctors with their specialty and room."""
    return tools.get_doctors()


@mcp.tool()
def find_doctors_by_specialty(specialty: str) -> list[dict]:
    """Find doctors whose specialty matches the given text (e.g. 'cardiology')."""
    return tools.find_doctors_by_specialty(specialty)


@mcp.tool()
def get_availability(doctor_id: int) -> list[dict]:
    """Return a doctor's open appointment slots."""
    return tools.get_availability(doctor_id)


@mcp.tool()
def book_appointment(patient_id: int, doctor_id: int, slot_id: int, reason: str = "") -> dict:
    """Book an open slot for a patient. Fails if the slot is already booked."""
    return tools.book_appointment(patient_id, doctor_id, slot_id, reason)


@mcp.tool()
def get_patient(patient_id: int) -> dict:
    """Look up a patient's basic profile."""
    return tools.get_patient(patient_id)


@mcp.tool()
def find_patient_by_name(first_name: str, last_name: str) -> list[dict]:
    """Look up an existing patient by first and last name. Use this before
    registering a new patient, to check whether they already have a profile."""
    return tools.find_patient_by_name(first_name, last_name)


@mcp.tool()
def register_patient(
    name: str, email: str = "", phone: str = "", gender: str = "",
    date_of_birth: str = "", address: str = "", blood_group: str = "",
) -> dict:
    """Create a new patient profile from the details the patient gives you in
    chat. Only call this once you've confirmed (via find_patient_by_name) that
    they aren't already registered."""
    return tools.register_patient(
        name, email, phone, gender, date_of_birth or None, address, blood_group
    )


@mcp.tool()
def request_refill(patient_id: int, medication: str, notes: str = "") -> dict:
    """Submit a prescription refill request for the clinic to review. The
    patient must already be identified (patient_id known) before calling this."""
    return tools.request_refill(patient_id, medication, notes)


if __name__ == "__main__":
    init_db()
    # host/port go straight to run() — fastmcp 3 dropped the `settings` object
    # that fastmcp 2.2 needed them set on.
    mcp.run(
        transport=settings.mcp_transport,
        host=settings.mcp_host,
        port=settings.mcp_port,
    )
