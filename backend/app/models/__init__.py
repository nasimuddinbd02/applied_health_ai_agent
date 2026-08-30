"""SQLModel tables for the hospital domain, one module per bounded area.

Importing this package registers every table on ``SQLModel.metadata``, which is
what ``Database.init()`` needs in order to create them — so import models from
here (``from app.models import Patient``) rather than reaching into a submodule.
"""

from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.base import now_iso, today_iso, utcnow
from app.models.billing import Invoice, InvoiceLineItem
from app.models.chat import ChatMessage, Conversation
from app.models.clinical import Treatment
from app.models.people import Doctor, Patient
from app.models.pharmacy import Medicine, Prescription, RefillRequest
from app.models.scheduling import Appointment, AvailabilitySlot

__all__ = [
    "Appointment",
    "AuditEvent",
    "AvailabilitySlot",
    "ChatMessage",
    "Conversation",
    "Doctor",
    "Invoice",
    "InvoiceLineItem",
    "Medicine",
    "Patient",
    "Prescription",
    "RefillRequest",
    "Treatment",
    "User",
    "now_iso",
    "today_iso",
    "utcnow",
]
