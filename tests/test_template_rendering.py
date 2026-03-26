"""Integration tests: template rendering wired through service and routes."""

import re
from collections.abc import Iterable
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.application.ports import LLMResult, StreamEvent
from app.domain.prompt_template import PromptTemplateError
from app.main import app as main_app


# ── Helpers & fixtures ─────────────────────────────────────────────────────────


def _make_llm_result(text: str = "Reply") -> LLMResult:
    return LLMResult(text=text, model="gpt-4.1-mini", ttfb_ms=10, total_ms=50)


def _make_stream_events() -> Iterable[StreamEvent]:
    yield StreamEvent(type="delta", delta="Hi", model="gpt-4.1-mini", ttfb_ms=10, total_ms=0)
    yield StreamEvent(type="final", text="Hi", model="gpt-4.1-mini", ttfb_ms=10, total_ms=20)


@pytest.fixture
def mock_llm():
    mock = MagicMock()
    mock.complete.return_value = _make_llm_result()
    return mock


@pytest.fixture
def client_with_mock_llm(mock_llm):
    from app.api import routes as api_routes
    main_app.dependency_overrides[api_routes.get_llm] = lambda: mock_llm
    with TestClient(main_app) as c:
        yield c
    main_app.dependency_overrides.clear()


@pytest.fixture
def mock_llm_streaming():
    mock = MagicMock()
    mock.stream.return_value = list(_make_stream_events())
    mock.complete.return_value = _make_llm_result()
    return mock


@pytest.fixture
def client_with_mock_stream(mock_llm_streaming):
    from app.api import routes as api_routes
    main_app.dependency_overrides[api_routes.get_llm] = lambda: mock_llm_streaming
    with TestClient(main_app) as c:
        yield c
    main_app.dependency_overrides.clear()


def _create_template_prompt(client, slug: str, system_prompt: str) -> None:
    r = client.post("/prompts", json={"slug": slug, "name": "Test", "system_prompt": system_prompt})
    assert r.status_code == 201, r.json()


# ── Rendering ─────────────────────────────────────────────────────────────────


def test_template_tags_rendered_before_llm_call(client_with_mock_llm, mock_llm) -> None:
    """{{time:current}} must be replaced with a real datetime before the LLM receives it."""
    _create_template_prompt(client_with_mock_llm, "current-time-test", "Now: {{time:current}}.")

    r = client_with_mock_llm.post("/conversations", json={
        "messages": [{"role": "user", "content": "What time is it?"}],
        "prompt_slug": "current-time-test",
    })
    assert r.status_code == 200

    instructions = mock_llm.complete.call_args[0][0]
    assert "{{time:current}}" not in instructions
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", instructions), (
        f"Expected a rendered UTC datetime in instructions, got: {instructions!r}"
    )


def test_conversation_start_consistent_across_turns(client_with_mock_llm, mock_llm) -> None:
    """{{time:conversation-start}} must resolve to the same value on every turn."""
    _create_template_prompt(
        client_with_mock_llm,
        "start-time-test",
        "Started: {{time:conversation-start}}.",
    )
    mock_llm.complete.side_effect = [_make_llm_result("first reply"), _make_llm_result("second reply")]

    r1 = client_with_mock_llm.post("/conversations", json={
        "messages": [{"role": "user", "content": "hello"}],
        "prompt_slug": "start-time-test",
    })
    assert r1.status_code == 200
    cid = r1.json()["conversation_id"]

    r2 = client_with_mock_llm.post(f"/conversations/{cid}", json={
        "messages": [{"role": "user", "content": "hello again"}],
        "prompt_slug": "start-time-test",
    })
    assert r2.status_code == 200

    instructions_1 = mock_llm.complete.call_args_list[0][0][0]
    instructions_2 = mock_llm.complete.call_args_list[1][0][0]

    assert "{{time:conversation-start}}" not in instructions_1
    assert "{{time:conversation-start}}" not in instructions_2

    pattern = r"Started: (\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC)"
    start_1 = re.search(pattern, instructions_1).group(1)
    start_2 = re.search(pattern, instructions_2).group(1)
    assert start_1 == start_2, (
        f"conversation-start drifted between turns: {start_1!r} → {start_2!r}"
    )


# ── PromptTemplateError → 400 in non-streaming routes ─────────────────────────


def test_template_error_in_create_route_returns_400(client_with_mock_llm) -> None:
    """PromptTemplateError during create_and_chat must surface as HTTP 400."""
    with patch(
        "app.application.services.render_prompt",
        side_effect=PromptTemplateError("Bad tag '{{oops}}'"),
    ):
        r = client_with_mock_llm.post("/conversations", json={
            "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 400
    assert "Bad tag" in r.json()["detail"]


def test_template_error_in_append_route_returns_400(client_with_mock_llm, mock_llm) -> None:
    """PromptTemplateError during append_and_chat must surface as HTTP 400, not 404."""
    r1 = client_with_mock_llm.post("/conversations", json={
        "messages": [{"role": "user", "content": "first"}],
    })
    cid = r1.json()["conversation_id"]

    with patch(
        "app.application.services.render_prompt",
        side_effect=PromptTemplateError("Bad tag '{{oops}}'"),
    ):
        r2 = client_with_mock_llm.post(f"/conversations/{cid}", json={
            "messages": [{"role": "user", "content": "second"}],
        })
    assert r2.status_code == 400
    assert "Bad tag" in r2.json()["detail"]


# ── PromptTemplateError → done SSE error in streaming routes ──────────────────


def test_template_error_in_create_stream_emits_error_done(client_with_mock_stream) -> None:
    """PromptTemplateError during create_and_stream must emit a done SSE error event."""
    with patch(
        "app.application.services.render_prompt",
        side_effect=PromptTemplateError("Bad tag '{{oops}}'"),
    ):
        r = client_with_mock_stream.post("/conversations/stream", json={
            "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 200
    body = b"".join(r.iter_bytes()).decode()
    assert "event: done" in body
    assert '"error"' in body
    assert "Bad tag" in body


def test_template_error_in_append_stream_emits_error_done(
    client_with_mock_stream, mock_llm_streaming
) -> None:
    """PromptTemplateError during append_and_stream must emit a done SSE error event."""
    r1 = client_with_mock_stream.post("/conversations", json={
        "messages": [{"role": "user", "content": "first"}],
    })
    assert r1.status_code == 200
    cid = r1.json()["conversation_id"]

    mock_llm_streaming.stream.return_value = list(_make_stream_events())
    with patch(
        "app.application.services.render_prompt",
        side_effect=PromptTemplateError("Bad tag '{{oops}}'"),
    ):
        r2 = client_with_mock_stream.post(f"/conversations/{cid}/stream", json={
            "messages": [{"role": "user", "content": "second"}],
        })
    assert r2.status_code == 200
    body = b"".join(r2.iter_bytes()).decode()
    assert "event: done" in body
    assert '"error"' in body
    assert "Bad tag" in body
