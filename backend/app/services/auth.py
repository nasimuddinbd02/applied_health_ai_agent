"""Authentication business logic: password hashing + JWT issue/verify.

Feature code never touches passlib/jose directly — it goes through this
provider, mirroring how ``AIGatewayService`` is the sole entry point for LLM
calls.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import Settings
from app.models import User
from app.repositories.user import UserRepository

ROLES = ("admin", "doctor", "receptionist", "patient")


class AuthError(Exception):
    """Raised on bad credentials, unknown role, or an invalid/expired token."""


class AuthService:
    def __init__(self, settings: Settings, users: UserRepository) -> None:
        self._settings = settings
        self._users = users

    # ----------------------------------------------------------------- #
    # Registration / password handling
    # ----------------------------------------------------------------- #
    def hash_password(self, plain: str) -> str:
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

    def email_exists(self, email: str) -> bool:
        return self._users.get_by_email(email) is not None

    def create_user(
        self, email: str, password: str, role: str,
        patient_id: int | None = None, doctor_id: int | None = None,
    ) -> User:
        if role not in ROLES:
            raise AuthError(f"Unknown role '{role}'.")
        if self._users.get_by_email(email):
            raise AuthError(f"Email '{email}' is already registered.")
        return self._users.create_user(
            email=email, hashed_password=self.hash_password(password), role=role,
            patient_id=patient_id, doctor_id=doctor_id,
        )

    # ----------------------------------------------------------------- #
    # Login / tokens
    # ----------------------------------------------------------------- #
    def login(self, email: str, password: str) -> tuple[str, User]:
        user = self._users.get_by_email(email)
        if user is None or not user.is_active or not self.verify_password(password, user.hashed_password):
            raise AuthError("Invalid email or password.")
        return self._issue_token(user), user

    def _issue_token(self, user: User) -> str:
        expires = datetime.now(UTC) + timedelta(minutes=self._settings.jwt_expire_minutes)
        payload = {"sub": str(user.id), "role": user.role, "exp": expires}
        return jwt.encode(payload, self._settings.jwt_secret, algorithm=self._settings.jwt_algorithm)

    def current_user(self, token: str) -> User:
        try:
            payload = jwt.decode(token, self._settings.jwt_secret, algorithms=[self._settings.jwt_algorithm])
        except JWTError as err:
            raise AuthError("Invalid or expired token.") from err
        user = self._users.get_by_id(int(payload["sub"]))
        if user is None or not user.is_active:
            raise AuthError("User not found or inactive.")
        return user
