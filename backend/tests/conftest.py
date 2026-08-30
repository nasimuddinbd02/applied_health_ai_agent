"""Pytest fixtures: force mock mode and seed a fresh DB once per session."""

import os

# Tests exercise the services / data layer and the MCP tools directly — no LLM
# calls — against a throwaway database.
os.environ.setdefault("DATABASE_URL", "sqlite:///database/test_hospital.db")
# The realtime layer must be correct on a single instance with no Redis, so the
# default suite runs it that way and exercises every in-process fallback.
# ``tests/test_redis_integration.py`` opts back in and skips if Redis is down.
os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("REDIS_NAMESPACE", "cityhospital-test")
os.environ.setdefault("SERVER_ID", "test-server-1")

import pytest

from app.db.seed import seed
from app.db.session import init_db


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    init_db()
    seed()
    yield
