"""Pharmacy business logic: medicine stock intake and prescribing.

Prescribing is delegated to the repository's atomic ``prescribe`` so stock can
never go negative or be partially decremented.
"""

from app.dbacces.pharmacy_repository import PharmacyRepository

LOW_STOCK_THRESHOLD = 10


class PharmacyError(Exception):
    """Raised on an invalid pharmacy request (unknown medicine, short stock)."""


class PharmacyProvider:
    def __init__(self, pharmacy_repo: PharmacyRepository) -> None:
        self._pharmacy = pharmacy_repo

    # ----------------------------------------------------------------- #
    # Medicines / stock
    # ----------------------------------------------------------------- #
    def list_medicines(self) -> list[dict]:
        return [self._medicine_dict(m) for m in self._pharmacy.list_medicines()]

    def add_medicine(self, name: str, dosage_form: str = "", unit: str = "",
                     stock_count: int = 0, unit_price: float = 0.0) -> dict:
        if not name.strip():
            raise PharmacyError("Medicine name is required.")
        medicine = self._pharmacy.create_medicine(
            name=name.strip(), dosage_form=dosage_form, unit=unit,
            stock_count=max(0, stock_count), unit_price=max(0.0, unit_price),
        )
        return self._medicine_dict(medicine)

    def restock(self, medicine_id: int, amount: int) -> dict:
        medicine = self._pharmacy.adjust_stock(medicine_id, amount)
        if medicine is None:
            raise PharmacyError(f"Medicine {medicine_id} not found.")
        return self._medicine_dict(medicine)

    def low_stock(self, threshold: int = LOW_STOCK_THRESHOLD) -> list[dict]:
        return [m for m in self.list_medicines() if m["stock_count"] <= threshold]

    # ----------------------------------------------------------------- #
    # Prescriptions
    # ----------------------------------------------------------------- #
    def prescribe(self, treatment_id: int, items: list[dict]) -> dict:
        """Prescribe a list of medicines for a treatment. Items:
        ``[{medicine_id, quantity, frequency, duration_days}]``."""
        clean = [i for i in items if i.get("medicine_id") and i.get("quantity", 0) > 0]
        if not clean:
            return {"created": []}
        result = self._pharmacy.prescribe(treatment_id, clean)
        if "error" in result:
            raise PharmacyError(result["error"])
        return result

    def prescriptions_for_treatment(self, treatment_id: int) -> list[dict]:
        rows = self._pharmacy.list_by_treatment(treatment_id)
        medicines = {m.id: m for m in self._pharmacy.list_medicines()}
        out: list[dict] = []
        for rx in rows:
            med = medicines.get(rx.medicine_id)
            out.append({
                "id": rx.id, "medicine_id": rx.medicine_id,
                "medicine_name": med.name if med else f"Medicine #{rx.medicine_id}",
                "unit": med.unit if med else "",
                "quantity": rx.quantity, "frequency": rx.frequency,
                "duration_days": rx.duration_days, "dispensed_at": rx.dispensed_at,
            })
        return out

    # ----------------------------------------------------------------- #
    # Helpers
    # ----------------------------------------------------------------- #
    @staticmethod
    def _medicine_dict(m) -> dict:
        return {
            "id": m.id, "name": m.name, "dosage_form": m.dosage_form, "unit": m.unit,
            "stock_count": m.stock_count, "unit_price": m.unit_price,
        }
