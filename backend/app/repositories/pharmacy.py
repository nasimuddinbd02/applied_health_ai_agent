"""Pharmacy data access: medicine stock and prescriptions.

The ``prescribe`` write is a single atomic transaction — it checks stock for
every requested item and decrements it as the prescriptions are created, so a
partial/over-stock prescription can never be persisted.
"""

from sqlmodel import select

from app.models import Medicine, Prescription, utcnow
from app.repositories.base import BaseRepository


class PharmacyRepository(BaseRepository):
    # ----------------------------------------------------------------- #
    # Medicines
    # ----------------------------------------------------------------- #
    def list_medicines(self) -> list[Medicine]:
        with self._session() as s:
            return list(s.exec(select(Medicine).order_by(Medicine.name)).all())

    def get_medicine(self, medicine_id: int) -> Medicine | None:
        with self._session() as s:
            return s.get(Medicine, medicine_id)

    def create_medicine(self, **fields) -> Medicine:
        with self._session() as s:
            medicine = Medicine(**fields)
            s.add(medicine)
            s.commit()
            s.refresh(medicine)
            return medicine

    def adjust_stock(self, medicine_id: int, delta: int) -> Medicine | None:
        with self._session() as s:
            medicine = s.get(Medicine, medicine_id)
            if medicine is None:
                return None
            medicine.stock_count = max(0, medicine.stock_count + delta)
            s.add(medicine)
            s.commit()
            s.refresh(medicine)
            return medicine

    # ----------------------------------------------------------------- #
    # Prescriptions
    # ----------------------------------------------------------------- #
    def prescribe(self, treatment_id: int, items: list[dict]) -> dict:
        """Atomically dispense every item: validate stock, decrement it, and
        create the Prescription rows in one transaction. Returns an error dict
        (no rows written) if any item is unknown or short on stock."""
        with self._session() as s:
            # Validate everything first — nothing is written until all pass.
            # Rows are locked in a fixed order (by medicine id): two concurrent
            # prescriptions sharing medicines would otherwise be able to grab
            # them in opposite orders and deadlock on PostgreSQL. The lock is
            # held to commit, so the decrement below sees what we validated.
            for item in sorted(items, key=lambda i: i["medicine_id"]):
                medicine = s.get(Medicine, item["medicine_id"], with_for_update=True)
                if medicine is None:
                    return {"error": f"Medicine {item['medicine_id']} does not exist."}
                if medicine.stock_count < item["quantity"]:
                    return {
                        "error": f"Not enough '{medicine.name}' in stock "
                        f"({medicine.stock_count} left, {item['quantity']} requested)."
                    }

            created: list[int] = []
            for item in items:
                medicine = s.get(Medicine, item["medicine_id"])
                medicine.stock_count -= item["quantity"]
                s.add(medicine)
                rx = Prescription(
                    treatment_id=treatment_id, medicine_id=item["medicine_id"],
                    quantity=item["quantity"], frequency=item.get("frequency", ""),
                    duration_days=item.get("duration_days", 0),
                )
                s.add(rx)
                s.flush()
                created.append(rx.id)
            s.commit()
            return {"created": created}

    def list_by_treatment(self, treatment_id: int) -> list[Prescription]:
        with self._session() as s:
            return list(
                s.exec(
                    select(Prescription).where(Prescription.treatment_id == treatment_id)
                    .order_by(Prescription.id)
                ).all()
            )

    def mark_dispensed(self, prescription_id: int) -> Prescription | None:
        with self._session() as s:
            rx = s.get(Prescription, prescription_id)
            if rx is None:
                return None
            rx.dispensed_at = utcnow()
            s.add(rx)
            s.commit()
            s.refresh(rx)
            return rx
