"""Pydantic request/response DTOs for the API layer."""

from pydantic import BaseModel


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class PatientCreate(BaseModel):
    name: str
    email: str = ""
    phone: str = ""
    gender: str = ""
    date_of_birth: str | None = None
    address: str = ""
    blood_group: str = ""
    notes: str = ""


class AppointmentRequest(BaseModel):
    patient_id: int
    doctor_id: int
    slot_id: int
    reason: str = ""


class PrescriptionItem(BaseModel):
    medicine_id: int
    quantity: int = 1
    frequency: str = ""
    duration_days: int = 0


class TreatmentCreate(BaseModel):
    diagnosis: str = ""
    prescription: str = ""
    notes: str = ""
    prescriptions: list[PrescriptionItem] = []


class MedicineCreate(BaseModel):
    name: str
    dosage_form: str = ""
    unit: str = ""
    stock_count: int = 0
    unit_price: float = 0.0


class AgentRequest(BaseModel):
    patient_id: int | None = None
    message: str
    thread_id: str | None = None


class DoctorCreate(BaseModel):
    name: str
    specialty: str = ""
    room: str = ""
    bio: str = ""
    phone: str = ""
    consultation_fee: float = 0.0
    login_email: str
    login_password: str


class DoctorUpdate(BaseModel):
    name: str | None = None
    specialty: str | None = None
    room: str | None = None
    bio: str | None = None
    phone: str | None = None
    consultation_fee: float | None = None


class ScheduleTemplate(BaseModel):
    weekdays: list[int]  # 0=Mon … 6=Sun
    start_time: str  # "HH:MM"
    end_time: str  # "HH:MM"
    slot_minutes: int = 30
    weeks: int = 2
    start_date: str | None = None  # ISO date; defaults to today


class LoginRequest(BaseModel):
    email: str
    password: str


class PatientSignupRequest(BaseModel):
    email: str
    password: str
    name: str
    phone: str = ""
    gender: str = ""
    date_of_birth: str | None = None
    address: str = ""
    blood_group: str = ""


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class AgentResponse(BaseModel):
    thread_id: str
    final_text: str
    transcript: list[dict]
    tool_calls: list[dict]


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    name: str = ""  # display name: the linked patient's/doctor's name
    patient_id: int | None = None
    doctor_id: int | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
