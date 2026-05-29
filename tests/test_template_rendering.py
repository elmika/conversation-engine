"""Integration tests: template rendering wired through service and routes."""

import re
import tempfile
from collections.abc import Iterable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.application.ports import LLMResult, StreamEvent
from app.domain.prompt_template import PromptTemplateError
from app.main import app as main_app
from tests.conftest import TEST_USER


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

    r = client_with_mock_llm.post(f"/u/{TEST_USER}/conversations", json={
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

    r1 = client_with_mock_llm.post(f"/u/{TEST_USER}/conversations", json={
        "messages": [{"role": "user", "content": "hello"}],
        "prompt_slug": "start-time-test",
    })
    assert r1.status_code == 200
    cid = r1.json()["conversation_id"]

    r2 = client_with_mock_llm.post(f"/u/{TEST_USER}/conversations/{cid}", json={
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
        r = client_with_mock_llm.post(f"/u/{TEST_USER}/conversations", json={
            "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 400
    assert "Bad tag" in r.json()["detail"]


def test_template_error_in_append_route_returns_400(client_with_mock_llm, mock_llm) -> None:
    """PromptTemplateError during append_and_chat must surface as HTTP 400, not 404."""
    r1 = client_with_mock_llm.post(f"/u/{TEST_USER}/conversations", json={
        "messages": [{"role": "user", "content": "first"}],
    })
    cid = r1.json()["conversation_id"]

    with patch(
        "app.application.services.render_prompt",
        side_effect=PromptTemplateError("Bad tag '{{oops}}'"),
    ):
        r2 = client_with_mock_llm.post(f"/u/{TEST_USER}/conversations/{cid}", json={
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
        r = client_with_mock_stream.post(f"/u/{TEST_USER}/conversations/stream", json={
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
    r1 = client_with_mock_stream.post(f"/u/{TEST_USER}/conversations", json={
        "messages": [{"role": "user", "content": "first"}],
    })
    assert r1.status_code == 200
    cid = r1.json()["conversation_id"]

    mock_llm_streaming.stream.return_value = list(_make_stream_events())
    with patch(
        "app.application.services.render_prompt",
        side_effect=PromptTemplateError("Bad tag '{{oops}}'"),
    ):
        r2 = client_with_mock_stream.post(f"/u/{TEST_USER}/conversations/{cid}/stream", json={
            "messages": [{"role": "user", "content": "second"}],
        })
    assert r2.status_code == 200
    body = b"".join(r2.iter_bytes()).decode()
    assert "event: done" in body
    assert '"error"' in body
    assert "Bad tag" in body


# ── File section tags ─────────────────────────────────────────────────────────


@pytest.fixture
def sections_dir(tmp_path):
    """Temporary sections directory with <TEST_USER>.md and default.md files for each tag.

    The render-preview endpoint uses get_preview_service which resolves slots
    with user_id="default", so default.md must also exist alongside the per-user file.
    """
    for tag in ("course", "user", "progress"):
        (tmp_path / tag).mkdir()
        (tmp_path / tag / f"{TEST_USER}.md").write_text(f"# {tag.capitalize()} Content")
        (tmp_path / tag / "default.md").write_text(f"# {tag.capitalize()} Content")
    return tmp_path


@pytest.fixture
def client_with_sections(mock_llm, sections_dir):
    """Test client with mock LLM and a custom sections_dir injected via settings override."""
    from app.api import routes as api_routes
    from app.settings import Settings

    def _override_settings():
        s = Settings()
        s.sections_dir = str(sections_dir)
        return s

    main_app.dependency_overrides[api_routes.get_llm] = lambda: mock_llm
    main_app.dependency_overrides[api_routes.get_settings] = _override_settings
    with TestClient(main_app) as c:
        yield c
    main_app.dependency_overrides.clear()


def test_file_section_resolved_before_llm_call(client_with_sections, mock_llm, sections_dir) -> None:
    """{{course}} must be expanded with file content before the LLM receives instructions."""
    (sections_dir / "course" / f"{TEST_USER}.md").write_text("Docker for CI/CD")
    _create_template_prompt(client_with_sections, "section-test", "Context: {{course}}")

    r = client_with_sections.post(f"/u/{TEST_USER}/conversations", json={
        "messages": [{"role": "user", "content": "hi"}],
        "prompt_slug": "section-test",
    })
    assert r.status_code == 200

    instructions = mock_llm.complete.call_args[0][0]
    assert "{{course}}" not in instructions
    assert "Docker for CI/CD" in instructions


def test_missing_section_file_returns_400(client_with_sections, sections_dir) -> None:
    """Missing section file at render time must return 400."""
    # Remove the course file so it's missing
    (sections_dir / "course" / f"{TEST_USER}.md").unlink()
    _create_template_prompt(client_with_sections, "missing-section", "{{course}}")

    r = client_with_sections.post(f"/u/{TEST_USER}/conversations", json={
        "messages": [{"role": "user", "content": "hi"}],
        "prompt_slug": "missing-section",
    })
    assert r.status_code == 400
    assert "Section file not found" in r.json()["detail"]


def test_section_containing_time_tag_resolved_end_to_end(
    client_with_sections, mock_llm, sections_dir
) -> None:
    """Section file content containing {{time:current}} is resolved in Pass 2."""
    (sections_dir / "user" / f"{TEST_USER}.md").write_text("Time: {{time:current}}")
    _create_template_prompt(client_with_sections, "time-in-section", "{{user}}")

    r = client_with_sections.post(f"/u/{TEST_USER}/conversations", json={
        "messages": [{"role": "user", "content": "hi"}],
        "prompt_slug": "time-in-section",
    })
    assert r.status_code == 200

    instructions = mock_llm.complete.call_args[0][0]
    assert "{{time:current}}" not in instructions
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", instructions)


def test_render_endpoint_returns_section_content(client_with_sections, sections_dir) -> None:
    """GET /prompts/{slug}/render must include expanded section content."""
    # Write to both the per-user file and default.md; the render endpoint
    # uses get_preview_service which resolves with user_id="default".
    (sections_dir / "course" / f"{TEST_USER}.md").write_text("# Rendered Course")
    (sections_dir / "course" / "default.md").write_text("# Rendered Course")
    _create_template_prompt(client_with_sections, "render-section-test", "Course: {{course}}")

    r = client_with_sections.get("/prompts/render-section-test/render")
    assert r.status_code == 200
    data = r.json()
    assert "{{course}}" not in data["rendered_prompt"]
    assert "# Rendered Course" in data["rendered_prompt"]
