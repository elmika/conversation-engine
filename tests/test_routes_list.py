"""Integration tests for GET /u/{user_id}/conversations, messages, and GET /prompts."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.application.ports import LLMResult
from app.main import app as main_app
from tests.conftest import TEST_USER


def _make_llm_result(text: str = "Reply") -> LLMResult:
    return LLMResult(text=text, model="gpt-4.1-mini", ttfb_ms=10, total_ms=50)


@pytest.fixture
def client():
    """Test client with mocked LLM; uses in-memory SQLite from conftest."""
    from app.api import routes as api_routes

    mock_llm = MagicMock()
    mock_llm.complete.return_value = _make_llm_result()
    main_app.dependency_overrides[api_routes.get_llm] = lambda: mock_llm
    with TestClient(main_app) as c:
        yield c
    main_app.dependency_overrides.clear()


def _create_conversation(client, message: str = "Hi") -> str:
    r = client.post(
        f"/u/{TEST_USER}/conversations",
        json={"messages": [{"role": "user", "content": message}]},
    )
    assert r.status_code == 200
    return r.json()["conversation_id"]


# --- GET /u/{user_id}/conversations ---


def test_list_conversations_response_shape(client) -> None:
    """Response has the correct envelope shape regardless of DB state."""
    r = client.get(f"/u/{TEST_USER}/conversations")
    assert r.status_code == 200
    data = r.json()
    assert "conversations" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert isinstance(data["conversations"], list)
    assert data["total"] == len(data["conversations"])  # default page_size >= conversations in test DB


def test_list_conversations_returns_created(client) -> None:
    """A newly created conversation appears in the list."""
    r_before = client.get(f"/u/{TEST_USER}/conversations")
    total_before = r_before.json()["total"]

    cid = _create_conversation(client)

    r = client.get(f"/u/{TEST_USER}/conversations?page_size=100")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == total_before + 1
    ids = [c["id"] for c in data["conversations"]]
    assert cid in ids
    assert "created_at" in next(c for c in data["conversations"] if c["id"] == cid)


def test_list_conversations_pagination(client) -> None:
    """Verify page_size limits results and page/page_size fields are echoed back."""
    from app.api import routes as api_routes
    from app.infra.persistence.db import get_engine
    from sqlalchemy import text

    mock_llm = main_app.dependency_overrides.get(api_routes.get_llm)
    if mock_llm:
        mock_llm().complete.side_effect = None
        mock_llm().complete.return_value = _make_llm_result()

    engine = get_engine()
    for _ in range(5):
        r = client.post(
            f"/u/{TEST_USER}/conversations",
            json={"messages": [{"role": "user", "content": "Ping"}]},
        )
        if r.status_code == 200:
            cid = r.json()["conversation_id"]
            # End the conversation directly in the DB so the next creation is allowed
            with engine.connect() as conn:
                conn.execute(
                    text("UPDATE conversations SET ended_at = CURRENT_TIMESTAMP WHERE id = :id"),
                    {"id": cid},
                )
                conn.commit()

    r = client.get(f"/u/{TEST_USER}/conversations?page=1&page_size=2")
    assert r.status_code == 200
    data = r.json()
    # Total includes all conversations created across the test session
    assert data["total"] >= 5
    assert len(data["conversations"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2

    r2 = client.get(f"/u/{TEST_USER}/conversations?page=2&page_size=2")
    data2 = r2.json()
    assert len(data2["conversations"]) == 2
    assert data2["page"] == 2


# --- GET /u/{user_id}/conversations/{id}/messages ---


def test_get_conversation_messages(client) -> None:
    cid = _create_conversation(client, "Hello there")
    r = client.get(f"/u/{TEST_USER}/conversations/{cid}/messages")
    assert r.status_code == 200
    data = r.json()
    assert data["conversation_id"] == cid
    msgs = data["messages"]
    assert len(msgs) == 2  # user message + assistant message
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Hello there"
    assert msgs[1]["role"] == "assistant"
    assert "id" in msgs[0]
    assert "created_at" in msgs[0]


def test_get_conversation_messages_unknown_id(client) -> None:
    # Unknown (or unowned) conversation ids are not enumerable — both return 404.
    r = client.get(f"/u/{TEST_USER}/conversations/nonexistent-id/messages")
    assert r.status_code == 404


# --- Cross-user ownership isolation ---

OTHER_USER = "other-user"


def test_other_user_cannot_read_messages(client) -> None:
    """A conversation owned by TEST_USER is not readable under another user_id."""
    cid = _create_conversation(client)
    r = client.get(f"/u/{OTHER_USER}/conversations/{cid}/messages")
    assert r.status_code == 404


def test_other_user_cannot_rename(client) -> None:
    """Renaming another user's conversation returns 404 and does not change the name."""
    cid = _create_conversation(client)
    r = client.patch(
        f"/u/{OTHER_USER}/conversations/{cid}", json={"name": "hijacked"}
    )
    assert r.status_code == 404
    # Owner still sees the conversation (rename did not apply).
    owner = client.get(f"/u/{TEST_USER}/conversations?page_size=100").json()
    name = next(c["name"] for c in owner["conversations"] if c["id"] == cid)
    assert name != "hijacked"


def test_other_user_cannot_delete(client) -> None:
    """Deleting another user's conversation is a no-op; the owner's conversation survives."""
    cid = _create_conversation(client)
    r = client.delete(f"/u/{OTHER_USER}/conversations/{cid}")
    assert r.status_code == 204  # idempotent delete — no information leak
    # Owner's conversation still exists.
    owner = client.get(f"/u/{TEST_USER}/conversations/{cid}/messages")
    assert owner.status_code == 200


def test_other_user_cannot_end_session(client) -> None:
    """Ending another user's conversation returns 404."""
    cid = _create_conversation(client)
    r = client.post(f"/u/{OTHER_USER}/conversations/{cid}/end-session")
    assert r.status_code == 404


# --- GET /prompts (root — no user prefix) ---


def test_get_prompts(client) -> None:
    r = client.get("/prompts")
    assert r.status_code == 200
    data = r.json()
    assert "prompts" in data
    prompts = data["prompts"]
    assert len(prompts) >= 1
    slugs = [p["slug"] for p in prompts]
    assert "default" in slugs
    for p in prompts:
        assert "slug" in p
        assert "name" in p
        assert "system_prompt" in p


def test_get_prompts_includes_all_registered(client) -> None:
    r = client.get("/prompts")
    data = r.json()
    returned_slugs = {p["slug"] for p in data["prompts"]}
    # Both prompts from the prompts/ directory should be seeded
    assert "default" in returned_slugs
    assert "conflict-coach-v1" in returned_slugs
