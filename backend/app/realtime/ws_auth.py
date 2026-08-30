"""WebSocket handshake authentication (design doc §16).

Identity is settled **once, at connection establishment**, and then carried on
the connection. Two kinds of caller:

* an authenticated user — bearer JWT passed as ``?token=`` (browsers cannot
  set headers on a WebSocket handshake) or, for non-browser clients, the
  ``Authorization`` header. Their patient/doctor binding comes from the User
  row, never from the request.
* an anonymous visitor — the clinic deliberately lets strangers chat and book.
  They get a **server-minted, signed guest session token**, returned in the
  ``ready`` event and replayed on reconnect. It carries a session id and
  nothing else; any patient identity later resolved by the agent is bound to
  that session id server-side, in Redis.

Either way the browser never gets to assert "I am patient 7".
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from starlette.websockets import WebSocket

from app.core.config import Settings
from app.services.auth import AuthError, AuthService

GUEST_ROLE = "guest"


@dataclass
class ChatPrincipal:
    """Who is on the other end of a chat connection."""

    session_id: str
    kind: str  # "user" | "guest"
    role: str = GUEST_ROLE
    user_id: int | None = None
    patient_id: int | None = None
    display_name: str = ""
    session_token: str = ""

    @property
    def is_guest(self) -> bool:
        return self.kind == GUEST_ROLE

    def to_session_values(self) -> dict:
        return {
            "kind": self.kind,
            "role": self.role,
            "user_id": self.user_id,
            "patient_id": self.patient_id,
            "patient_name": self.display_name,
        }


class WebSocketAuthenticator:
    def __init__(self, settings: Settings, auth: AuthService) -> None:
        self._settings = settings
        self._auth = auth

    # ----------------------------------------------------------------- #
    # Handshake
    # ----------------------------------------------------------------- #
    def authenticate(self, websocket: WebSocket) -> ChatPrincipal:
        """Resolve the principal for a pending WebSocket handshake."""
        return self.authenticate_token(self._extract_token(websocket))

    def authenticate_token(self, token: str | None) -> ChatPrincipal:
        """Resolve a principal from a raw token. Shared with the REST fallback.

        Never raises for an *absent* token — anonymous chat is a product
        requirement. A token that is present but invalid is also downgraded to
        a guest rather than refused: an expired tab should keep talking to the
        assistant, it just stops being a privileged session.
        """
        if not token:
            return self._new_guest()

        # A guest token is our own; try it first so a returning visitor keeps
        # the session (and therefore the identity) they had before reconnecting.
        guest = self._decode_guest(token)
        if guest is not None:
            return guest

        try:
            user = self._auth.current_user(token)
        except AuthError:
            return self._new_guest()

        return ChatPrincipal(
            session_id=f"user-{user.id}",
            kind="user",
            role=user.role,
            user_id=user.id,
            patient_id=user.patient_id,
            session_token=token,
        )

    @staticmethod
    def _extract_token(websocket: WebSocket) -> str:
        token = websocket.query_params.get("token", "")
        if token:
            return token
        header = websocket.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            return header[7:].strip()
        return ""

    # ----------------------------------------------------------------- #
    # Guest sessions
    # ----------------------------------------------------------------- #
    def _new_guest(self) -> ChatPrincipal:
        session_id = f"guest-{uuid.uuid4().hex[:16]}"
        return ChatPrincipal(
            session_id=session_id,
            kind=GUEST_ROLE,
            role=GUEST_ROLE,
            session_token=self.issue_guest_token(session_id),
        )

    def issue_guest_token(self, session_id: str) -> str:
        expires = datetime.now(UTC) + timedelta(
            minutes=self._settings.guest_session_expire_minutes
        )
        payload = {"sub": session_id, "role": GUEST_ROLE, "exp": expires}
        return jwt.encode(
            payload, self._settings.jwt_secret, algorithm=self._settings.jwt_algorithm
        )

    def _decode_guest(self, token: str) -> ChatPrincipal | None:
        try:
            payload = jwt.decode(
                token, self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
            )
        except JWTError:
            return None
        if payload.get("role") != GUEST_ROLE:
            return None
        session_id = str(payload.get("sub") or "")
        if not session_id.startswith("guest-"):
            return None
        return ChatPrincipal(
            session_id=session_id, kind=GUEST_ROLE, role=GUEST_ROLE, session_token=token
        )
