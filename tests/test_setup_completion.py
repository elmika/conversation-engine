"""Tests for the setup-completion flow (extraction + atomic file writes + ordering)."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.learning.setup_completion as sc
from app.application.ports import LLMResult
from app.learning.setup_completion import SetupCompletionError, complete_setup
from app.main import app as main_app
from tests.conftest import TEST_USER


class _FakePromptRepo:
    def get_prompt(self, slug: str) -> dict:
        return {"slug": slug, "name": slug, "system_prompt": f"sys-{slug}", "model": None}


class _FakeLLM:
    """Returns a distinct text per call so we can tell profile vs outline apart."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, instructions, messages, model=None) -> dict:
        self.calls += 1
        return {"text": f"extracted-{self.calls}", "model": "m", "ttfb_ms": 1, "total_ms": 1}

    def stream(self, *args, **kwargs):  # pragma: no cover - unused
        raise NotImplementedError


def test_complete_setup_writes_both_files(tmp_path) -> None:
    """Happy path: profile → user file, outline → course file."""
    complete_setup(
        [{"role": "user", "content": "hi"}], _FakePromptRepo(), _FakeLLM(), str(tmp_path), "u1"
    )
    # Call order is profile(1) then outline(2); course holds the outline, user the profile.
    assert (tmp_path / "course" / "u1.md").read_text() == "extracted-2"
    assert (tmp_path / "user" / "u1.md").read_text() == "extracted-1"


def test_complete_setup_seeds_initial_progress(tmp_path) -> None:
    """An initial progress file is seeded so the first course session can render {{progress}}."""
    complete_setup(
        [{"role": "user", "content": "hi"}], _FakePromptRepo(), _FakeLLM(), str(tmp_path), "u1"
    )
    progress = (tmp_path / "progress" / "u1.md").read_text()
    # Matches the four-section shape progress-synthesis produces, in a first-session state.
    assert progress.startswith("## What the student knows")
    assert "## Progress - Current state" in progress
    # Not LLM-generated — the fake LLM is only called twice (profile + outline).
    assert "extracted-" not in progress


def test_complete_setup_user_file_written_last(tmp_path, monkeypatch) -> None:
    """If the user-file write fails, the course file exists but the has_profile signal does not."""
    real = sc._atomic_write

    def flaky(path, content):
        if path.parent.name == "user":
            raise OSError("disk full")
        real(path, content)

    monkeypatch.setattr(sc, "_atomic_write", flaky)

    with pytest.raises(SetupCompletionError):
        complete_setup(
            [{"role": "user", "content": "hi"}], _FakePromptRepo(), _FakeLLM(), str(tmp_path), "u1"
        )

    assert (tmp_path / "course" / "u1.md").exists()
    assert (tmp_path / "progress" / "u1.md").exists()
    assert not (tmp_path / "user" / "u1.md").exists()  # has_profile stays false → retryable


def test_atomic_write_leaves_no_temp_file(tmp_path) -> None:
    target = tmp_path / "x.md"
    sc._atomic_write(target, "content")
    assert target.read_text() == "content"
    assert list(tmp_path.glob("*.tmp")) == []


# --- Route-level recoverability ---


@pytest.fixture
def client():
    from app.api import routes as api_routes

    mock_llm = MagicMock()
    mock_llm.complete.return_value = LLMResult(
        text="Reply", model="gpt-4.1-mini", ttfb_ms=1, total_ms=1
    )
    main_app.dependency_overrides[api_routes.get_llm] = lambda: mock_llm
    with TestClient(main_app) as c:
        yield c, mock_llm
    main_app.dependency_overrides.clear()


def test_complete_setup_failure_keeps_conversation_active(client) -> None:
    """When extraction fails, the conversation must NOT be ended — the learner can retry."""
    c, mock_llm = client
    cid = c.post(
        f"/u/{TEST_USER}/conversations",
        json={"messages": [{"role": "user", "content": "hi"}]},
    ).json()["conversation_id"]

    # Make the extraction LLM calls fail.
    mock_llm.complete.side_effect = RuntimeError("boom")
    r = c.post(f"/u/{TEST_USER}/conversations/{cid}/complete-setup")
    assert r.status_code == 500

    # Conversation is still active (not ended) and remains fetchable.
    mock_llm.complete.side_effect = None
    msgs = c.get(f"/u/{TEST_USER}/conversations/{cid}/messages")
    assert msgs.status_code == 200
    assert msgs.json()["ended_at"] is None
