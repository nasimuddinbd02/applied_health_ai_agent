"""Composition root: instantiate and wire every class once (dependency injection).

Import the singletons from here (``from app.core.container import container``) in
controllers, the MCP server, the agent worker and tests. Construction is cheap
and lazy — no model, network or Redis calls happen until the application
actually starts.

Layers, top to bottom:

    api/           controllers (REST routes + the /ws/chat gateway) and deps
    realtime/      transport: connections, registry, dispatcher, protocol
    workers/       the agent worker that consumes the event bus
    services/      business logic (appointments, chat, conversations, AI gateway)
    messaging/     Redis client, event bus
    repositories/  data access + the conversation cache
    db/            engine, sessions, migrations, seed data
    models/        SQLModel tables      schemas/  Pydantic DTOs
    core/          settings, prompts, errors, safety, coordination, this file
"""

from app.core.config import settings
from app.core.coordination import IdempotencyGuard, RateLimiter
from app.core.prompts import PromptRegistry
from app.core.safety import SafetyGuard
from app.db.session import Database, database
from app.messaging.event_bus import EventBus, InProcessEventBus
from app.messaging.redis_client import RedisClient
from app.messaging.redis_event_bus import RedisStreamEventBus
from app.realtime.connection_manager import ConnectionManager
from app.realtime.dispatcher import RealtimeDispatcher
from app.realtime.session_registry import SessionRegistry
from app.realtime.ws_auth import WebSocketAuthenticator
from app.repositories.ai import AiRepository
from app.repositories.billing import BillingRepository
from app.repositories.conversation import ConversationRepository
from app.repositories.conversation_cache import ConversationCache
from app.repositories.domain import DomainRepository
from app.repositories.pharmacy import PharmacyRepository
from app.repositories.user import UserRepository
from app.services.admin import AdminService
from app.services.agent import AgentService
from app.services.ai_gateway import AIGatewayService
from app.services.appointment import AppointmentService
from app.services.auth import AuthService
from app.services.billing import BillingService
from app.services.chat import ChatService
from app.services.conversation import ConversationService
from app.services.llm import LLMFactory
from app.services.pharmacy import PharmacyService
from app.services.reception import ReceptionService
from app.workers.agent_worker import AgentWorker


class Container:
    """Holds every wired singleton instance for the application."""

    def __init__(self, db: Database) -> None:
        self.database = db
        self.settings = settings

        # cross-cutting
        self.prompts = PromptRegistry()
        self.safety = SafetyGuard()
        self.llm_factory = LLMFactory(settings)

        # infrastructure
        self.redis = RedisClient(settings)
        self.idempotency = IdempotencyGuard(self.redis, settings)
        self.rate_limiter = RateLimiter(self.redis, settings)
        # Default to the in-process bus. ``select_event_bus`` swaps in the Redis
        # Streams bus at startup, once we know whether Redis actually came up.
        self.event_bus: EventBus = InProcessEventBus(
            max_attempts=settings.event_max_delivery_attempts
        )

        # data access
        self.domain_repo = DomainRepository(db)
        self.ai_repo = AiRepository(db)
        self.user_repo = UserRepository(db)
        self.billing_repo = BillingRepository(db)
        self.pharmacy_repo = PharmacyRepository(db)
        self.conversation_repo = ConversationRepository(db)
        self.conversation_cache = ConversationCache(self.redis, settings)

        # realtime transport
        self.connections = ConnectionManager()
        self.session_registry = SessionRegistry(self.redis, settings)
        self.dispatcher = RealtimeDispatcher(
            self.redis, self.session_registry, self.connections, settings
        )

        # providers (business logic)
        self.billing = BillingService(self.domain_repo, self.billing_repo)
        self.pharmacy = PharmacyService(self.pharmacy_repo)
        self.appointments = AppointmentService(self.domain_repo, billing=self.billing)
        self.auth = AuthService(settings, self.user_repo)
        self.admin = AdminService(self.domain_repo, self.auth)
        self.reception = ReceptionService(self.domain_repo)
        self.conversations = ConversationService(
            self.conversation_repo, self.conversation_cache,
            history_turns=settings.conversation_history_turns,
        )
        self.agent = AgentService(settings, self.llm_factory, self.prompts)
        self.gateway = AIGatewayService(
            settings, self.ai_repo, self.safety, self.llm_factory, self.agent
        )
        self.chat = ChatService(
            self.conversations, self.event_bus, self.idempotency, self.rate_limiter
        )
        self.ws_auth = WebSocketAuthenticator(settings, self.auth)

        # worker
        self.agent_worker = AgentWorker(
            self.event_bus, self.gateway, self.conversations, self.dispatcher,
            self.session_registry, self.idempotency, settings,
        )
        # Last-resort path when the bus rejects a publish mid-conversation.
        self.chat.set_degraded_runner(self.agent_worker.handle)

    # ----------------------------------------------------------------- #
    # Startup wiring
    # ----------------------------------------------------------------- #
    def select_event_bus(self) -> EventBus:
        """Pick the real bus now that Redis connectivity is known.

        Called once from the application (or worker) startup, *after*
        ``redis.connect()``. With Redis up this is the durable Redis Streams
        bus, so agent work survives a restart and can be consumed by workers on
        other instances; without it, the in-process queue keeps a single
        instance fully functional.
        """
        if self.redis.available:
            self.event_bus = RedisStreamEventBus(self.redis, self.settings)
        self.chat.use_event_bus(self.event_bus)
        self.agent_worker.use_event_bus(self.event_bus)
        return self.event_bus


# Application-wide singleton.
container = Container(database)
