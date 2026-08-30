"""Auth controller: login, current-user lookup, and patient self-signup."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.models import User
from app.schemas import LoginRequest, PatientSignupRequest, TokenResponse, UserOut
from app.services.appointment import AppointmentService
from app.services.auth import AuthError, AuthService


class AuthController:
    def __init__(self, auth: AuthService, appointments: AppointmentService) -> None:
        self._auth = auth
        self._appt = appointments
        self.router = APIRouter(prefix="/api/auth", tags=["auth"])
        self._register()

    def _register(self) -> None:
        r = self.router
        r.add_api_route("/login", self.login, methods=["POST"])
        r.add_api_route("/me", self.me, methods=["GET"])
        r.add_api_route("/register", self.register, methods=["POST"])

    def login(self, body: LoginRequest):
        try:
            token, user = self._auth.login(body.email, body.password)
        except AuthError as err:
            raise HTTPException(401, str(err)) from err
        return TokenResponse(access_token=token, user=self._user_out(user))

    def me(self, user: User = Depends(get_current_user)):
        return self._user_out(user)

    def register(self, body: PatientSignupRequest):
        """Patient self-signup: creates the Patient profile + the login User together."""
        patient = self._appt.register_patient({
            "name": body.name, "email": body.email, "phone": body.phone,
            "gender": body.gender, "date_of_birth": body.date_of_birth,
            "address": body.address, "blood_group": body.blood_group,
        })
        try:
            user = self._auth.create_user(
                body.email, body.password, role="patient", patient_id=patient.id,
            )
        except AuthError as err:
            raise HTTPException(400, str(err)) from err
        token, _ = self._auth.login(body.email, body.password)
        return TokenResponse(access_token=token, user=self._user_out(user))

    def _user_out(self, user: User) -> UserOut:
        """Attach a human display name: the linked patient/doctor record's name."""
        name = ""
        if user.patient_id:
            patient = self._appt.get_patient(user.patient_id)
            name = patient.name if patient else ""
        elif user.doctor_id:
            doctor = self._appt.get_doctor(user.doctor_id)
            name = doctor.name if doctor else ""
        return UserOut(
            id=user.id, email=user.email, role=user.role, name=name,
            patient_id=user.patient_id, doctor_id=user.doctor_id,
        )
