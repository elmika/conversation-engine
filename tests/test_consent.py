"""Tests for the GDPR consent gate: GET/POST /u/{user_id}/consent, and
server-side enforcement on conversation-creation routes."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import routes as api_routes
from app.application.ports import LLMResult
from app.main import app as main_app


def _make_llm_result(text: str = "Reply") -> LLMResult:
    return LLMResult(
        text=text, model="gpt-4.1", ttfb_ms=10, total_ms=50, input_tokens=0, output_tokens=0
    )


@pytest.fixture
def client():
    """Test client with the real require_consent gate active (opts out of the
    blanket bypass conftest.py applies for every other test)."""
    mock_llm = MagicMock()
    mock_llm.complete.return_value = _make_llm_result()
    main_app.dependency_overrides[api_routes.get_llm] = lambda: mock_llm
    main_app.dependency_overrides.pop(api_routes.require_consent, None)
    with TestClient(main_app) as c:
        yield c
    main_app.dependency_overrides.clear()


@pytest.fixture
def user_id() -> str:
    """A fresh, never-before-seen user_id per test — consent_records is not
    reset between tests (correctly: consent shouldn't be wiped like
    conversations are), so a shared constant would leak state across tests."""
    return f"consent-test-{uuid.uuid4()}"


def test_consent_status_false_for_fresh_user(client, user_id):
    r = client.get(f"/u/{user_id}/consent")
    assert r.status_code == 200
    assert r.json() == {"consented": False, "consented_at": None}


def test_record_consent_then_status_true(client, user_id):
    r = client.post(f"/u/{user_id}/consent")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "recorded"
    assert body["consented_at"] is not None

    r2 = client.get(f"/u/{user_id}/consent")
    assert r2.status_code == 200
    assert r2.json()["consented"] is True
    assert r2.json()["consented_at"] == body["consented_at"]


def test_recording_consent_twice_is_idempotent(client, user_id):
    r1 = client.post(f"/u/{user_id}/consent")
    r2 = client.post(f"/u/{user_id}/consent")
    assert r1.json()["consented_at"] == r2.json()["consented_at"]


def test_conversation_creation_rejected_without_consent(client, user_id):
    r = client.post(
        f"/u/{user_id}/conversations",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert r.status_code == 403


def test_conversation_creation_allowed_after_consent(client, user_id):
    client.post(f"/u/{user_id}/consent")
    r = client.post(
        f"/u/{user_id}/conversations",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert r.status_code == 200


def test_consent_is_per_user(client, user_id):
    """Recording consent for one user_id must not grant it to another."""
    client.post(f"/u/{user_id}/consent")
    r = client.get(f"/u/{user_id}-other/consent")
    assert r.json()["consented"] is False
