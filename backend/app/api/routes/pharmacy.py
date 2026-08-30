"""Pharmacy controller: medicine stock + a treatment's prescriptions.

Listing medicines and reading prescriptions is open to any authenticated user
(doctors need the catalogue to prescribe; patients can see their own meds);
adding stock is admin-only.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_role
from app.schemas import MedicineCreate
from app.services.pharmacy import PharmacyService

_AUTH = Depends(get_current_user)
_ADMIN = Depends(require_role("admin"))


class PharmacyController:
    def __init__(self, pharmacy: PharmacyService) -> None:
        self._pharmacy = pharmacy
        self.router = APIRouter(prefix="/api", tags=["pharmacy"])
        self._register()

    def _register(self) -> None:
        r = self.router
        r.add_api_route("/medicines", self.list_medicines, methods=["GET"], dependencies=[_AUTH])
        r.add_api_route("/medicines", self.add_medicine, methods=["POST"], dependencies=[_ADMIN])
        r.add_api_route("/treatments/{treatment_id}/prescriptions", self.prescriptions,
                        methods=["GET"], dependencies=[_AUTH])

    def list_medicines(self):
        return self._pharmacy.list_medicines()

    def add_medicine(self, body: MedicineCreate):
        return self._pharmacy.add_medicine(
            body.name, body.dosage_form, body.unit, body.stock_count, body.unit_price
        )

    def prescriptions(self, treatment_id: int):
        return self._pharmacy.prescriptions_for_treatment(treatment_id)
