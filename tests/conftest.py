"""Pytest fixtures."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# In-memory SQLite for tests (db.init_engine uses StaticPool so one connection is shared).
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Stable user_id used across all HTTP-level tests.
TEST_USER = "test-user"

from app.main import app


@pytest.fixture(autouse=True)
def reset_conversations():
    """Delete all conversations (and cascading messages/runs) between tests.

    The in-memory DB is shared across all tests via StaticPool. Without this cleanup,
    an active conversation created in one test blocks new-conversation creation in the next
    (only one active conversation is allowed at a time).
    """
    yield
    try:
        from app.infra.persistence.db import get_engine
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM runs"))
            conn.execute(text("DELETE FROM messages"))
            conn.execute(text("DELETE FROM conversations"))
            conn.commit()
    except Exception:
        pass  # Engine not yet initialised in very early tests — safe to ignore


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    return TestClient(app)
