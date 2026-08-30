"""FastAPI auth dependencies: resolve the bearer token to a User, gate routes by role.

Used across controllers as ``Depends(require_role("admin", "receptionist"))`` —
keeps role checks declarative on the route instead of duplicated in each
handler body.
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models import User
from app.services.auth import AuthError

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    # Imported lazily: authz is imported by every controller, and importing the
    # container at module load would create an import cycle (container wires
    # providers, which the controllers also import).
    from app.core.container import container

    if creds is None:
        raise HTTPException(401, "Not authenticated.")
    try:
        return container.auth.current_user(creds.credentials)
    except AuthError as err:
        raise HTTPException(401, str(err)) from err


def require_role(*roles: str):
    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"Requires role in {roles}, got '{user.role}'.")
        return user

    return _dependency
