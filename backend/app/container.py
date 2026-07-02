"""Composition root: instantiate and wire every class once (dependency injection).

Import the singletons from here (``from app.container import container``) in
controllers, the MCP server and tests. Construction is cheap and lazy — no
model/network calls happen until the agent actually runs online.
"""

from app.common.config import settings
from app.common.prompts import PromptRegistry
from app.dbacces.ai_repository import AiRepository
from app.dbacces.billing_repository import BillingRepository
from app.dbacces.database import Database, database
from app.dbacces.domain_repository import DomainRepository
from app.dbacces.pharmacy_repository import PharmacyRepository
from app.dbacces.user_repository import UserRepository
from app.lib.safety import SafetyGuard
from app.providers.admin_provider import AdminProvider
from app.providers.agent_provider import AgentProvider
from app.providers.appointment_provider import AppointmentProvider
from app.providers.auth_provider import AuthProvider
from app.providers.billing_provider import BillingProvider
from app.providers.gateway_provider import GatewayProvider
from app.providers.llm_factory import LLMFactory
from app.providers.pharmacy_provider import PharmacyProvider
from app.providers.reception_provider import ReceptionProvider


class Container:
    """Holds every wired singleton instance for the application."""

    def __init__(self, db: Database) -> None:
        self.database = db
        self.settings = settings

        # cross-cutting
        self.prompts = PromptRegistry()
        self.safety = SafetyGuard()
        self.llm_factory = LLMFactory(settings)

        # data access
        self.domain_repo = DomainRepository(db)
        self.ai_repo = AiRepository(db)
        self.user_repo = UserRepository(db)
        self.billing_repo = BillingRepository(db)
        self.pharmacy_repo = PharmacyRepository(db)

        # providers (business logic)
        self.billing = BillingProvider(self.domain_repo, self.billing_repo)
        self.pharmacy = PharmacyProvider(self.pharmacy_repo)
        self.appointments = AppointmentProvider(self.domain_repo, billing=self.billing)
        self.auth = AuthProvider(settings, self.user_repo)
        self.admin = AdminProvider(self.domain_repo, self.auth)
        self.reception = ReceptionProvider(self.domain_repo)
        self.agent = AgentProvider(
            settings, self.appointments, self.llm_factory, self.prompts
        )
        self.gateway = GatewayProvider(
            settings, self.ai_repo, self.safety, self.llm_factory, self.agent
        )


# Application-wide singleton.
container = Container(database)
