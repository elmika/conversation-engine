"""Integration test: a course conversation hits TWO different prompts.

The opening turn uses the INTRO prompt (course-session-init); every subsequent
turn uses the CORE prompt (course-session-core). This proves the phase→prompt
mapping is wired through the service, not just unit-tested in isolation.

Uses the non-streaming routes (create_and_chat → append_and_chat) with a mocked
LLM, so we can inspect exactly which system prompt each turn received.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.application.ports import LLMResult
from app.main import app as main_app
from tests.conftest import TEST_USER


@pytest.fixture
def mock_llm():
    mock = MagicMock()
    mock.complete.side_effect = [
        LLMResult(text="opening", model="gpt-4.1", ttfb_ms=10, total_ms=50),
        LLMResult(text="reply", model="gpt-4.1", ttfb_ms=10, total_ms=50),
    ]
    return mock


@pytest.fixture
def sections_dir(tmp_path):
    for tag in ("course", "user", "progress"):
        (tmp_path / tag).mkdir()
        (tmp_path / tag / f"{TEST_USER}.md").write_text(f"# {tag.capitalize()} Content")
        (tmp_path / tag / "default.md").write_text(f"# {tag.capitalize()} Content")
    return tmp_path


@pytest.fixture
def client_with_sections(mock_llm, sections_dir):
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


def test_opening_uses_init_prompt_subsequent_uses_core_prompt(
    client_with_sections, mock_llm
) -> None:
    # Turn 1: create the conversation with the course flow.
    r1 = client_with_sections.post(
        f"/u/{TEST_USER}/conversations",
        json={
            "messages": [{"role": "user", "content": "start"}],
            "prompt_slug": "course-session-init",
        },
    )
    assert r1.status_code == 200, r1.json()
    cid = r1.json()["conversation_id"]

    # Turn 2: a subsequent turn on the same conversation.
    r2 = client_with_sections.post(
        f"/u/{TEST_USER}/conversations/{cid}",
        json={"messages": [{"role": "user", "content": "go on"}]},
    )
    assert r2.status_code == 200, r2.json()

    instructions_turn1 = mock_llm.complete.call_args_list[0][0][0]
    instructions_turn2 = mock_llm.complete.call_args_list[1][0][0]

    # Turn 1 = INTRO prompt: drives the opening message / module list.
    assert "drives only your opening message" in instructions_turn1
    assert "The session is already open" not in instructions_turn1

    # Turn 2 = CORE prompt: continues the lesson, never re-emits the opening.
    assert "The session is already open" in instructions_turn2
    assert "drives only your opening message" not in instructions_turn2
