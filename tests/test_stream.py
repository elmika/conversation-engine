"""Tests for streaming conversation endpoint with mocked LLM."""

from collections.abc import Iterable
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.application.ports import StreamEvent
from app.main import app
from app.settings import Settings


def _make_events() -> Iterable[StreamEvent]:
    yield StreamEvent(type="delta", delta="Hel", model="gpt-4.1-mini", ttfb_ms=10, total_ms=0)
    yield StreamEvent(type="delta", delta="lo", model="gpt-4.1-mini", ttfb_ms=10, total_ms=0)
    yield StreamEvent(type="final", text="Hello", model="gpt-4.1-mini", ttfb_ms=10, total_ms=20)


@pytest.fixture
def mock_llm_streaming():
    """Inject a mock LLM adapter with stream + complete."""
    mock = MagicMock()
    mock.stream.return_value = list(_make_events())
    # complete is unused here but some routes depend on it.
    mock.complete.return_value = {
        "text": "Hi there",
        "model": "gpt-4.1-mini",
        "ttfb_ms": 50,
        "total_ms": 100,
    }
    return mock


@pytest.fixture
def client_with_mock_stream(mock_llm_streaming):
    """Override get_llm to return mock_llm_streaming."""
    from app.api import routes

    app.dependency_overrides[routes.get_llm] = lambda: mock_llm_streaming
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_conversation_stream_sends_meta_chunk_done(
    client_with_mock_stream, mock_llm_streaming
) -> None:
    """POST /conversations/{conversation_id}/stream emits meta, chunk, done, and includes history."""
    # First create a conversation to obtain a valid id.
    create_resp = client_with_mock_stream.post(
        "/conversations",
        json={
            "messages": [{"role": "user", "content": "First"}],
        },
    )
    assert create_resp.status_code == 200
    cid = create_resp.json()["conversation_id"]

    # Stream a new turn on that conversation.
    response = client_with_mock_stream.post(
        f"/conversations/{cid}/stream",
        json={
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 200
    body = b"".join(response.iter_bytes()).decode("utf-8")

    # Basic structure checks.
    assert "event: meta" in body
    assert "event: chunk" in body
    assert "event: done" in body

    # Ensure deltas are present.
    assert '"delta": "Hel"' in body or '"delta":"Hel"' in body
    assert '"delta": "lo"' in body or '"delta":"lo"' in body

    # Done payload should include timings and assistant_message.
    assert '"assistant_message": "Hello"' in body or '"assistant_message":"Hello"' in body
    assert '"ttfb_ms": 10' in body
    assert '"total_ms": 20' in body

    # LLM stream call should see prior user + assistant messages as history.
    assert mock_llm_streaming.stream.call_count == 1
    _, messages_arg = mock_llm_streaming.stream.call_args[0]
    roles = [m["role"] for m in messages_arg]
    contents = [m["content"] for m in messages_arg]
    # History for streaming append: user \"First\", assistant \"Hi there\", plus new user \"Hello\".
    assert roles == ["user", "assistant", "user"]
    assert contents == ["First", "Hi there", "Hello"]


def test_conversation_stream_first_turn_creates_conversation(
    client_with_mock_stream, mock_llm_streaming
) -> None:
    """POST /conversations/stream streams the first turn and creates a conversation."""
    response = client_with_mock_stream.post(
        "/conversations/stream",
        json={
            "messages": [{"role": "user", "content": "Hello from scratch"}],
        },
    )
    assert response.status_code == 200
    body = b"".join(response.iter_bytes()).decode("utf-8")

    # Should emit meta, chunk, and done, with a conversation_id.
    assert "event: meta" in body
    assert "event: chunk" in body
    assert "event: done" in body
    assert '"assistant_message": "Hello"' in body or '"assistant_message":"Hello"' in body


def test_conversation_stream_rejects_input_over_max_chars(client_with_mock_stream) -> None:
    """POST /conversations/stream returns 400 when total message content exceeds max_input_chars."""
    from app.api import routes

    app.dependency_overrides[routes.get_settings] = lambda: Settings(max_input_chars=10)
    try:
        response = client_with_mock_stream.post(
            "/conversations/stream",
            json={
                "messages": [{"role": "user", "content": "way over ten chars here"}],
            },
        )
        assert response.status_code == 400
        assert "max_input_chars" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(routes.get_settings, None)


def test_conversation_stream_emits_done_on_llm_error(client_with_mock_stream) -> None:
    """POST /conversations/stream emits done event with error when LLM adapter raises HTTPException."""
    from app.api import routes
    from fastapi import HTTPException

    mock_llm = MagicMock()
    mock_llm.stream.side_effect = HTTPException(status_code=429, detail="Rate limit exceeded")

    app.dependency_overrides[routes.get_llm] = lambda: mock_llm
    try:
        response = client_with_mock_stream.post(
            "/conversations/stream",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert response.status_code == 200
        body = b"".join(response.iter_bytes()).decode("utf-8")

        # Should emit done event with error
        assert "event: done" in body
        assert '"error"' in body
        assert '"type": "http_error"' in body or '"type":"http_error"' in body
        assert '"status_code": 429' in body or '"status_code":429' in body
        assert "Rate limit exceeded" in body
    finally:
        app.dependency_overrides.pop(routes.get_llm, None)


def test_conversation_stream_append_emits_done_on_llm_error(client_with_mock_stream) -> None:
    """POST /conversations/{id}/stream emits done event with error when LLM adapter raises HTTPException."""
    from app.api import routes
    from fastapi import HTTPException

    # First create a conversation
    create_resp = client_with_mock_stream.post(
        "/conversations",
        json={
            "messages": [{"role": "user", "content": "First"}],
        },
    )
    assert create_resp.status_code == 200
    cid = create_resp.json()["conversation_id"]

    # Now mock LLM to raise error on append
    mock_llm = MagicMock()
    mock_llm.stream.side_effect = HTTPException(status_code=504, detail="Upstream timeout")

    app.dependency_overrides[routes.get_llm] = lambda: mock_llm
    try:
        response = client_with_mock_stream.post(
            f"/conversations/{cid}/stream",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert response.status_code == 200
        body = b"".join(response.iter_bytes()).decode("utf-8")

        # Should emit done event with error
        assert "event: done" in body
        assert '"error"' in body
        assert '"type": "http_error"' in body or '"type":"http_error"' in body
        assert '"status_code": 504' in body or '"status_code":504' in body
        assert "Upstream timeout" in body
    finally:
        app.dependency_overrides.pop(routes.get_llm, None)

