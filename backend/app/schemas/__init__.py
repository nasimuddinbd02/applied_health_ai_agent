"""Pydantic DTOs for the API layer, plus the internal agent result type.

Kept separate from ``app.models`` (the SQLModel tables): what the API accepts
and returns is a contract, and it should be free to differ from how rows are
stored.
"""

from app.schemas.agent import AgentRequest, AgentResponse
from app.schemas.appointment import AppointmentRequest, PrescriptionItem, TreatmentCreate
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.schemas.doctor import DoctorCreate, DoctorUpdate, ScheduleTemplate
from app.schemas.patient import PatientCreate, PatientSignupRequest
from app.schemas.pharmacy import MedicineCreate
from app.schemas.results import AgentResult

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "AgentResult",
    "AppointmentRequest",
    "DoctorCreate",
    "DoctorUpdate",
    "LoginRequest",
    "MedicineCreate",
    "PatientCreate",
    "PatientSignupRequest",
    "PrescriptionItem",
    "ScheduleTemplate",
    "TokenResponse",
    "TreatmentCreate",
    "UserOut",
]
