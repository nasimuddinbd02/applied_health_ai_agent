"""Pharmacy DTOs."""

from pydantic import BaseModel


class MedicineCreate(BaseModel):
    name: str
    dosage_form: str = ""
    unit: str = ""
    stock_count: int = 0
    unit_price: float = 0.0
