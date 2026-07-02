"""Global domain-error → HTTP mapping, registered once on the FastAPI app.

Controllers raise (or let propagate) domain exceptions from the provider layer;
this registrar converts them to consistent JSON error responses, so routes
don't repeat ``try/except → HTTPException`` boilerplate.

``AuthError`` is intentionally NOT registered here: its status depends on
context (401 on login, 400 on duplicate signup), so the auth controller keeps
handling it locally.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.providers.admin_provider import AdminError
from app.providers.appointment_provider import AppointmentError
from app.providers.billing_provider import BillingError
from app.providers.pharmacy_provider import PharmacyError


class DomainErrorRegistrar:
    """Maps domain exception types to HTTP status codes on a FastAPI app."""

    # Every business-rule violation is a client error.
    _MAPPING: dict[type[Exception], int] = {
        AppointmentError: 400,
        AdminError: 400,
        BillingError: 400,
        PharmacyError: 400,
    }

    def register(self, app: FastAPI) -> None:
        for exc_type, status in self._MAPPING.items():
            app.add_exception_handler(exc_type, self._handler_for(status))

    @staticmethod
    def _handler_for(status: int):
        def _handle(request: Request, exc: Exception) -> JSONResponse:
            return JSONResponse(status_code=status, content={"detail": str(exc)})

        return _handle
