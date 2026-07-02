"""Pytest fixtures: force mock mode and seed a fresh DB once per session."""

import os

# Tests exercise the providers / data layer and the MCP tools directly — no LLM
# calls — against a throwaway database.
os.environ.setdefault("DATABASE_URL", "sqlite:///database/test_hospital.db")

import pytest

from app.dbacces.database import init_db
from app.seed import seed


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    init_db()
    seed()
    yield
