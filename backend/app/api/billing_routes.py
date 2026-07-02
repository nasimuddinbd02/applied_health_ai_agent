"""Billing controller: patient invoices + payment actions.

Reading an invoice is open to any authenticated user; changing its state
(pay / void) is restricted to front-desk / admin staff.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.lib.authz import get_current_user, require_role
from app.providers.billing_provider import BillingError, BillingProvider

_STAFF = Depends(require_role("receptionist", "admin"))
_AUTH = Depends(get_current_user)


class BillingController:
    def __init__(self, billing: BillingProvider) -> None:
        self._billing = billing
        self.router = APIRouter(prefix="/api", tags=["billing"])
        self._register()

    def _register(self) -> None:
        r = self.router
        r.add_api_route("/patients/{patient_id}/invoices", self.list_for_patient,
                        methods=["GET"], dependencies=[_AUTH])
        r.add_api_route("/invoices/{invoice_id}", self.get, methods=["GET"], dependencies=[_AUTH])
        r.add_api_route("/invoices/{invoice_id}/pay", self.pay, methods=["POST"], dependencies=[_STAFF])
        r.add_api_route("/invoices/{invoice_id}/void", self.void, methods=["POST"], dependencies=[_STAFF])

    def list_for_patient(self, patient_id: int):
        return self._billing.list_for_patient(patient_id)

    def get(self, invoice_id: int):
        # Local override: an unknown invoice id is a 404, not the global 400.
        try:
            return self._billing.get_with_items(invoice_id)
        except BillingError as err:
            raise HTTPException(404, str(err)) from err

    def pay(self, invoice_id: int):
        return self._billing.mark_paid(invoice_id)

    def void(self, invoice_id: int):
        return self._billing.void(invoice_id)
