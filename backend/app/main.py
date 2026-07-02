"""FastAPI application: controllers + CORS + startup DB init."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin_routes import AdminController
from app.api.agent_routes import AgentController
from app.api.appointment_routes import AppointmentController
from app.api.auth_routes import AuthController
from app.api.billing_routes import BillingController
from app.api.doctor_routes import DoctorController
from app.api.ops_routes import OpsController
from app.api.patient_routes import PatientController
from app.api.pharmacy_routes import PharmacyController
from app.api.reception_routes import ReceptionController
from app.container import container
from app.lib.error_handlers import DomainErrorRegistrar


@asynccontextmanager
async def lifespan(app: FastAPI):
    container.database.init()
    yield


app = FastAPI(title="City Hospital", version="1.0.0", lifespan=lifespan)

# Domain exceptions from the provider layer become consistent JSON errors —
# controllers stay free of try/except boilerplate.
DomainErrorRegistrar().register(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[container.settings.frontend_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire controllers from the DI container.
app.include_router(AuthController(container.auth, container.appointments).router)
app.include_router(PatientController(container.appointments).router)
app.include_router(DoctorController(container.appointments).router)
app.include_router(
    AppointmentController(container.appointments, container.billing, container.pharmacy).router
)
app.include_router(AgentController(container.gateway, container.appointments).router)
app.include_router(OpsController(container.ai_repo, container.appointments).router)
app.include_router(AdminController(container.admin).router)
app.include_router(ReceptionController(container.reception).router)
app.include_router(BillingController(container.billing).router)
app.include_router(PharmacyController(container.pharmacy).router)


@app.get("/health")
def health() -> dict:
    s = container.settings
    return {
        "status": "ok",
        "provider": s.primary_provider,
        "model": s.model_quality,
        "has_provider_key": s.has_provider_key,
    }
