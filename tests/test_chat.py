"""Tests for conversation endpoints with mocked LLM."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.application.ports import LLMResult
from app.main import app


def _make_llm_result(
    text: str = "Hi there",
    model: str = "gpt-4.1-mini",
    ttfb_ms: int = 50,
    total_ms: int = 100,
) -> LLMResult:
    return LLMResult(text=text, model=model, ttfb_ms=ttfb_ms, total_ms=total_ms)


@pytest.fixture
def mock_llm():
    """Inject a mock LLM adapter."""
    mock = MagicMock()
    mock.complete.return_value = _make_llm_result()
    return mock


@pytest.fixture
def client_with_mock_llm(mock_llm):
    """Override get_llm to return mock_llm."""
    from app.api import routes
    app.dependency_overrides[routes.get_llm] = lambda: mock_llm
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_conversations_create_returns_envelope(client_with_mock_llm, mock_llm) -> None:
    """POST /conversations returns conversation_id, assistant_message, model, timings."""
    response = client_with_mock_llm.post(
        "/conversations",
        json={
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "conversation_id" in data
    assert data["assistant_message"] == "Hi there"
    assert data["model"] == "gpt-4.1-mini"
    assert data["timings"]["ttfb_ms"] == 50
    assert data["timings"]["total_ms"] == 100
    mock_llm.complete.assert_called_once()
    call_args = mock_llm.complete.call_args
    assert "You are a concise and precise assistant." in (call_args[0][0] or "")
    assert call_args[0][1] == [{"role": "user", "content": "Hello"}]


def test_conversations_create_uses_prompt_slug(client_with_mock_llm, mock_llm) -> None:
    """POST /conversations with prompt_slug uses that prompt's system_prompt."""
    response = client_with_mock_llm.post(
        "/conversations",
        json={
            "prompt_slug": "conflict-coach-v1",
            "messages": [{"role": "user", "content": "A colleague disagrees."}],
        },
    )
    assert response.status_code == 200
    call_args = mock_llm.complete.call_args
    assert "workplace conflicts" in (call_args[0][0] or "")


def test_conversations_append_uses_path_conversation_id(client_with_mock_llm, mock_llm) -> None:
    """POST /conversations/{conversation_id} returns the same id."""
    # First create a conversation to obtain a valid id.
    create_resp = client_with_mock_llm.post(
        "/conversations",
        json={
            "messages": [{"role": "user", "content": "First"}],
        },
    )
    assert create_resp.status_code == 200
    cid = create_resp.json()["conversation_id"]

    # Append a new turn to the same conversation.
    append_resp = client_with_mock_llm.post(
        f"/conversations/{cid}",
        json={
            "messages": [{"role": "user", "content": "Hi again"}],
        },
    )
    assert append_resp.status_code == 200
    assert append_resp.json()["conversation_id"] == cid
