"""Application bootstrap: middleware, routers, and the realtime lifespan."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import build_router
from app.core.container import container
from app.core.errors import DomainErrorRegistrar

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bring the instance up as a chat gateway, then take it down cleanly.

    Order matters: Redis first (it decides which event bus we get), then the
    cross-server dispatcher so this instance can receive replies for the
    sockets it owns, then — in single-process deployments — the agent worker.
    """
    container.database.init()
    await container.redis.connect()
    bus = container.select_event_bus()
    await bus.start()
    await container.dispatcher.start()

    if container.settings.inline_agent_worker:
        await container.agent_worker.start()

    log.info(
        "Chat gateway ready: server_id=%s redis=%s bus=%s inline_worker=%s",
        container.settings.instance_id, container.redis.available, bus.name,
        container.settings.inline_agent_worker,
    )
    try:
        yield
    finally:
        # Connection draining (design doc §19): close sockets politely so
        # clients reconnect to a healthy instance instead of hanging.
        await container.connections.drain()
        if container.settings.inline_agent_worker:
            await container.agent_worker.stop()
        await container.dispatcher.stop()
        await bus.close()
        await container.redis.close()


app = FastAPI(title="City Hospital", version="2.0.0", lifespan=lifespan)

# Domain exceptions from the service layer become consistent JSON errors —
# controllers stay free of try/except boilerplate.
DomainErrorRegistrar().register(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[container.settings.frontend_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every REST controller and the WebSocket gateway, wired from the container.
app.include_router(build_router(container))


@app.get("/health", tags=["health"])
async def health() -> dict:
    s = container.settings
    return {
        "status": "ok",
        "server_id": s.instance_id,
        "provider": s.primary_provider,
        "model": s.model_quality,
        "has_provider_key": s.has_provider_key,
        "redis": container.redis.available,
        "event_bus": container.event_bus.name,
        "inline_agent_worker": s.inline_agent_worker,
        "active_connections": container.connections.count,
        "cluster_connections": await container.session_registry.connection_count(s.instance_id),
    }


@app.get("/health/live", tags=["health"])
def liveness() -> dict:
    """Process is up. Deliberately dependency-free: a Redis blip must not get
    the pod killed and drop every WebSocket it is holding."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict:
    """Ready to accept new connections."""
    return {"status": "ready", "redis": await container.redis.ping()}
