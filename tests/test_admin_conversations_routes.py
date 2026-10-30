"""Integration tests for GET /admin/conversations and .../messages (Piece C2)."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.application.ports import LLMResult
from app.main import app as main_app
from tests.conftest import ADMIN_HEADERS

USER_A = "admin-conv-test-user-a"
USER_B = "admin-conv-test-user-b"


def _make_llm_result(text: str = "Reply") -> LLMResult:
    return LLMResult(
        text=text, model="gpt-4.1", ttfb_ms=10, total_ms=50, input_tokens=0, output_tokens=0
    )


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


def _create_conversation(client, user_id: str, message: str = "Hi") -> str:
    r = client.post(
        f"/u/{user_id}/conversations",
        json={"messages": [{"role": "user", "content": message}]},
    )
    assert r.status_code == 200
    return r.json()["conversation_id"]


# --- GET /admin/conversations ---


def test_admin_list_conversations_requires_auth(client) -> None:
    r = client.get("/admin/conversations")
    assert r.status_code == 401


def test_admin_list_conversations_rejects_wrong_token(client) -> None:
    r = client.get("/admin/conversations", headers={"Authorization": "Bearer wrong-token"})
    assert r.status_code == 401


def test_admin_list_conversations_spans_all_users(client) -> None:
    """Conversations created by different users all appear, each with its own user_id."""
    cid_a = _create_conversation(client, USER_A, "From A")
    cid_b = _create_conversation(client, USER_B, "From B")

    r = client.get("/admin/conversations?page_size=100", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "conversations" in data and "total" in data and "page" in data and "page_size" in data

    by_id = {c["id"]: c for c in data["conversations"]}
    assert cid_a in by_id
    assert cid_b in by_id
    assert by_id[cid_a]["user_id"] == USER_A
    assert by_id[cid_b]["user_id"] == USER_B


def test_admin_list_conversations_pagination(client) -> None:
    from sqlalchemy import text

    from app.api import routes as api_routes
    from app.infra.persistence.db import get_engine

    mock_llm = main_app.dependency_overrides.get(api_routes.get_llm)
    if mock_llm:
        mock_llm().complete.side_effect = None
        mock_llm().complete.return_value = _make_llm_result()

    engine = get_engine()
    for i in range(5):
        cid = _create_conversation(client, f"admin-conv-page-user-{i}")
        # End immediately so it doesn't block that user's next active conversation
        # (irrelevant here since each i uses a fresh user, but keeps things tidy).
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE conversations SET ended_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"id": cid},
            )
            conn.commit()

    r = client.get("/admin/conversations?page=1&page_size=2", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 5
    assert len(data["conversations"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2

    r2 = client.get("/admin/conversations?page=2&page_size=2", headers=ADMIN_HEADERS)
    data2 = r2.json()
    assert len(data2["conversations"]) == 2
    assert data2["page"] == 2


# --- GET /admin/conversations/{id}/messages ---


def test_admin_get_messages_requires_auth(client) -> None:
    cid = _create_conversation(client, USER_A)
    r = client.get(f"/admin/conversations/{cid}/messages")
    assert r.status_code == 401


def test_admin_get_messages_reads_any_owner(client) -> None:
    """Unlike the per-user endpoint, admin can read a transcript regardless of owner."""
    cid = _create_conversation(client, USER_B, "Hello there")

    r = client.get(f"/admin/conversations/{cid}/messages", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["conversation_id"] == cid
    msgs = data["messages"]
    assert len(msgs) == 2  # user message + assistant message
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Hello there"
    assert msgs[1]["role"] == "assistant"


def test_admin_get_messages_unknown_id(client) -> None:
    r = client.get("/admin/conversations/nonexistent-id/messages", headers=ADMIN_HEADERS)
    assert r.status_code == 404
