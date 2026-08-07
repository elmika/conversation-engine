"""Pytest fixtures."""

import os
from collections.abc import Iterable
from typing import Optional
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.application.ports import LLMResult, StreamEvent

# In-memory SQLite for tests (db.init_engine uses StaticPool so one connection is shared).
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Stable user_id used across all HTTP-level tests.
TEST_USER = "test-user"


class FakeLLM:
    """Test double for LLMPort — never constructs an OpenAI client or hits the network.

    The lifespan builds this instead of OpenAILLMAdapter under test (see
    _no_real_llm_in_tests), so the suite needs no OPENAI_API_KEY and never talks
    to an external service. Tests that assert on specific model output override
    `get_llm` with their own mock; this fake just lets the app boot and serves
    tests that don't care what the model returns.
    """

    def __init__(self, settings: object = None) -> None:  # matches OpenAILLMAdapter(settings)
        pass

    def complete(
        self, instructions: str, messages: list[dict[str, str]], model: Optional[str] = None
    ) -> LLMResult:
        return LLMResult(
            text="", model=model or "fake", ttfb_ms=0, total_ms=0,
            input_tokens=0, output_tokens=0,
        )

    def stream(
        self, instructions: str, messages: list[dict[str, str]], model: Optional[str] = None
    ) -> Iterable[StreamEvent]:
        yield StreamEvent(
            type="final", text="", model=model or "fake", ttfb_ms=0, total_ms=0,
            input_tokens=0, output_tokens=0,
        )


@pytest.fixture(autouse=True, scope="session")
def _no_real_llm_in_tests():
    """Make the app lifespan build a FakeLLM instead of the real OpenAI adapter.

    Keeps unit tests off the external service: no credentials required, no
    network. Production is unaffected — it still builds OpenAILLMAdapter and
    fails fast on a missing key.
    """
    with patch("app.main.OpenAILLMAdapter", FakeLLM):
        yield


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
