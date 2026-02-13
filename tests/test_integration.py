"""Integration-style test: in-memory SQLite + mocked LLM, full conversation flow."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.application.ports import LLMResult
from app.main import app as main_app


def _make_llm_result(
    text: str,
    model: str = "gpt-4.1-mini",
    ttfb_ms: int = 50,
    total_ms: int = 100,
) -> LLMResult:
    return LLMResult(text=text, model=model, ttfb_ms=ttfb_ms, total_ms=total_ms)


@pytest.fixture
def mock_llm():
    """Mock LLM that returns deterministic replies."""
    mock = MagicMock()
    mock.complete.side_effect = [
        _make_llm_result("Hello back!"),
        _make_llm_result("Second reply."),
    ]
    return mock


@pytest.fixture
def client_with_mock_llm(mock_llm):
    """Override get_llm; use main app so lifespan and in-memory DB are used."""
    from app.api import routes as api_routes

    main_app.dependency_overrides[api_routes.get_llm] = lambda: mock_llm
    with TestClient(main_app) as c:
        yield c
    main_app.dependency_overrides.clear()


def test_integration_create_then_append_turn(client_with_mock_llm, mock_llm) -> None:
    """Full flow: create conversation, append turn; assert response shape and second call."""
    # Create conversation (first turn)
    r1 = client_with_mock_llm.post(
        "/conversations",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert r1.status_code == 200
    data1 = r1.json()
    cid = data1["conversation_id"]
    assert data1["assistant_message"] == "Hello back!"
    assert "timings" in data1

    # Append second turn
    r2 = client_with_mock_llm.post(
        f"/conversations/{cid}",
        json={"messages": [{"role": "user", "content": "Second"}]},
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["conversation_id"] == cid
    assert data2["assistant_message"] == "Second reply."

    # LLM was called twice: once for create, once for append.
    assert mock_llm.complete.call_count == 2
    # Second call receives the new turn only (current API does not pass prior messages).
    second_call_messages = mock_llm.complete.call_args_list[1][0][1]
    assert len(second_call_messages) == 1
    assert second_call_messages[0]["role"] == "user"
    assert second_call_messages[0]["content"] == "Second"
