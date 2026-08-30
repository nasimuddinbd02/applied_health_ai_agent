"""Authentication DTOs."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


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
