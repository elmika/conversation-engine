"""A learner-facing conversation request can't pick its own prompt or model.

Regression guard for the fix: ConversationRequest/InitSessionRequest/
ConversationRewindRequest no longer have prompt_slug/model_slug fields at all
(see their docstrings) — the override capability only exists on the mirrored
/admin/u/{user_id}/... routes, gated by require_admin. In-memory SQLite + a
mocked LLM, no network.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.application.ports import LLMResult
from app.main import app as main_app
from tests.conftest import ADMIN_HEADERS, TEST_USER

_PROMPTS = {
    "conflict-coach-v1": "workplace conflicts",
}


def _make_llm_result(text: str = "Reply", model: str = "gpt-4.1") -> LLMResult:
    return LLMResult(
        text=text, model=model, ttfb_ms=10, total_ms=50, input_tokens=0, output_tokens=0
    )


@pytest.fixture
def mock_llm():
    mock = MagicMock()
    mock.complete.return_value = _make_llm_result()
    return mock


@pytest.fixture
def client(mock_llm):
    from app.api import routes as api_routes

    main_app.dependency_overrides[api_routes.get_llm] = lambda: mock_llm
    with TestClient(main_app) as c:
        yield c
    main_app.dependency_overrides.clear()


def test_learner_route_ignores_client_supplied_model_slug(client, mock_llm):
    """POSTing model_slug on the learner route doesn't reach the LLM call —
    the field isn't in the schema, so it's silently dropped, not honored."""
    r = client.post(
        f"/u/{TEST_USER}/conversations",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "model_slug": "gpt-6-astra",
        },
    )
    assert r.status_code == 200, r.json()
    # model isn't in the learner-facing response at all (platform-internal
    # detail — see ConversationResponse's docstring), so assert against what
    # the LLM was actually called with instead: whatever the (mocked) default
    # resolution produced, never the attempted override.
    assert "model" not in r.json()
    assert mock_llm.complete.call_args.kwargs["model"] != "gpt-6-astra"


def test_learner_route_ignores_client_supplied_prompt_slug(client, mock_llm):
    """POSTing prompt_slug on the learner route doesn't select that prompt."""
    r = client.post(
        f"/u/{TEST_USER}/conversations",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "prompt_slug": "conflict-coach-v1",
        },
    )
    assert r.status_code == 200, r.json()
    # If the override had been honored, the mocked LLM would have received
    # conflict-coach-v1's system prompt; it never even loaded that far since
    # the field is dropped before reaching prompt resolution.
    call_instructions = mock_llm.complete.call_args[0][0]
    assert "workplace conflicts" not in call_instructions


def test_admin_route_requires_auth(client):
    """The admin conversation-turn route rejects an unauthenticated request."""
    r = client.post(
        f"/admin/u/{TEST_USER}/conversations",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 401


def test_admin_route_honors_model_slug_when_authenticated(client, mock_llm):
    """The admin route legitimately accepts and forwards a model override."""
    r = client.post(
        f"/admin/u/{TEST_USER}/conversations",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "model_slug": "gpt-5.4-mini",
        },
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200, r.json()
    assert mock_llm.complete.call_args.kwargs.get("model") == "gpt-5.4-mini"
