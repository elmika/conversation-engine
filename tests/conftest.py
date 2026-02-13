"""Pytest fixtures."""

import os

import pytest
from fastapi.testclient import TestClient

# In-memory SQLite for tests (db.init_engine uses StaticPool so one connection is shared).
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    return TestClient(app)
