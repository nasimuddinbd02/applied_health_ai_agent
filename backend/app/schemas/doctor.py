"""Doctor and schedule-builder DTOs."""

from pydantic import BaseModel


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
