"""Aggregates every controller into the single router `main.py` mounts.

Controllers are classes that take their collaborators from the DI container, so
the wiring lives here rather than in `main.py` — adding an endpoint module means
touching one file, and the application bootstrap stays about the application.
"""

from fastapi import APIRouter

from app.api.routes.admin import AdminController
from app.api.routes.agent import AgentController
from app.api.routes.appointments import AppointmentController
from app.api.routes.auth import AuthController
from app.api.routes.billing import BillingController
from app.api.routes.doctors import DoctorController
from app.api.routes.ops import OpsController
from app.api.routes.patients import PatientController
from app.api.routes.pharmacy import PharmacyController
from app.api.routes.reception import ReceptionController
from app.api.ws.chat import ChatWebSocketController
from app.core.container import Container


def build_router(container: Container) -> APIRouter:
    """Build the application router from a wired container."""
    router = APIRouter()

    controllers = [
        AuthController(container.auth, container.appointments),
        PatientController(container.appointments),
        DoctorController(container.appointments),
        AppointmentController(container.appointments, container.billing, container.pharmacy),
        AgentController(
            container.chat, container.conversations, container.agent_worker,
            container.ws_auth, container.session_registry, container.appointments,
            container.settings,
        ),
        # The realtime chat gateway. It is mounted alongside the REST
        # controllers because it is the same application — the socket just
        # happens to be the transport (see app/api/ws/chat.py).
        ChatWebSocketController(
            container.settings, container.ws_auth, container.connections,
            container.session_registry, container.dispatcher, container.conversations,
            container.chat,
        ),
        OpsController(container.ai_repo, container.appointments),
        AdminController(container.admin),
        ReceptionController(container.reception),
        BillingController(container.billing),
        PharmacyController(container.pharmacy),
    ]

    for controller in controllers:
        router.include_router(controller.router)
    return router
