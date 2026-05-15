"""Functional tests for conversation naming.

These tests caught the autoflush=False + session.get() bug where rename_conversation
silently did nothing because the pending Conversation object wasn't flushed to the DB
before the lookup, causing all conversations to be created with name=None.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.application.ports import LLMResult
from app.main import app as main_app


def _make_llm_result(text: str = "Reply") -> LLMResult:
    return LLMResult(text=text, model="gpt-4.1-mini", ttfb_ms=10, total_ms=50)


@pytest.fixture
def client():
    from app.api import routes as api_routes
    mock_llm = MagicMock()
    mock_llm.complete.return_value = _make_llm_result()
    main_app.dependency_overrides[api_routes.get_llm] = lambda: mock_llm
    with TestClient(main_app) as c:
        yield c
    main_app.dependency_overrides.clear()


def _end_conversation(cid: str) -> None:
    """End a conversation directly in the DB so the next one can be created."""
    from app.infra.persistence.db import get_engine
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE conversations SET ended_at = CURRENT_TIMESTAMP WHERE id = :id"),
            {"id": cid},
        )
        conn.commit()


def _create_conversation(client: TestClient) -> str:
    r = client.post(
        "/conversations",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert r.status_code == 200
    return r.json()["conversation_id"]


def _get_conversation(client: TestClient, cid: str) -> dict:
    r = client.get("/conversations?page_size=100")
    assert r.status_code == 200
    convs = r.json()["conversations"]
    return next((c for c in convs if c["id"] == cid), {})


# --- name is set on creation ---

def test_new_conversation_has_non_null_name(client) -> None:
    """Conversation name must be set (not None) immediately after creation."""
    cid = _create_conversation(client)
    conv = _get_conversation(client, cid)
    assert conv, f"Conversation {cid} not found in list"
    assert conv.get("name") is not None, "name must not be None after creation"
    assert conv["name"] != "", "name must not be empty after creation"


def test_new_conversation_name_appears_in_list(client) -> None:
    """GET /conversations must return the name field for newly created conversations."""
    cid = _create_conversation(client)
    r = client.get("/conversations?page_size=100")
    assert r.status_code == 200
    conv = next((c for c in r.json()["conversations"] if c["id"] == cid), None)
    assert conv is not None
    assert "name" in conv
    assert conv["name"] is not None


# --- deduplication suffix ---

def test_duplicate_name_gets_numeric_suffix(client) -> None:
    """Second conversation with the same base name gets a ' (2)' suffix."""
    cid1 = _create_conversation(client)
    conv1 = _get_conversation(client, cid1)
    base_name = conv1["name"]

    _end_conversation(cid1)
    cid2 = _create_conversation(client)
    conv2 = _get_conversation(client, cid2)

    assert conv2["name"] == f"{base_name} (2)", (
        f"Expected '{base_name} (2)', got '{conv2['name']}'"
    )


def test_third_conversation_gets_suffix_3(client) -> None:
    """Third conversation with the same base name gets a ' (3)' suffix."""
    cid1 = _create_conversation(client)
    base_name = _get_conversation(client, cid1)["name"]
    _end_conversation(cid1)

    cid2 = _create_conversation(client)
    _end_conversation(cid2)

    cid3 = _create_conversation(client)
    conv3 = _get_conversation(client, cid3)
    assert conv3["name"] == f"{base_name} (3)"
