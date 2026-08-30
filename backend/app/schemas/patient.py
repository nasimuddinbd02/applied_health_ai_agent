"""Patient request DTOs."""

from pydantic import BaseModel


class PatientCreate(BaseModel):
    name: str
    email: str = ""
    phone: str = ""
    gender: str = ""
    date_of_birth: str | None = None
    address: str = ""
    blood_group: str = ""
    notes: str = ""


class PatientSignupRequest(BaseModel):
    email: str
    password: str
    name: str
    phone: str = ""
    gender: str = ""
    date_of_birth: str | None = None
    address: str = ""
    blood_group: str = ""
