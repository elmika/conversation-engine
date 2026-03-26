"""Route-level tests: template validation on POST /prompts and PUT /prompts/{slug}."""

import pytest
from fastapi.testclient import TestClient

from app.main import app as main_app


@pytest.fixture
def client():
    with TestClient(main_app) as c:
        yield c


# ── POST /prompts ──────────────────────────────────────────────────────────────


def test_create_prompt_rejects_malformed_tag(client) -> None:
    """{{bad}} (no colon) must be rejected at save time with 400."""
    r = client.post("/prompts", json={
        "slug": "bad-template-1",
        "name": "Bad",
        "system_prompt": "The time is {{bad}}.",
    })
    assert r.status_code == 400
    assert "Malformed tag" in r.json()["detail"]


def test_create_prompt_rejects_unknown_namespace(client) -> None:
    """{{foo:bar}} (unknown namespace) must be rejected at save time with 400."""
    r = client.post("/prompts", json={
        "slug": "bad-template-2",
        "name": "Bad",
        "system_prompt": "Value: {{foo:bar}}.",
    })
    assert r.status_code == 400
    assert "Unknown namespace" in r.json()["detail"]


def test_create_prompt_rejects_unknown_tag_name(client) -> None:
    """{{time:whatever}} (bad tag within known namespace) must be rejected with 400."""
    r = client.post("/prompts", json={
        "slug": "bad-template-3",
        "name": "Bad",
        "system_prompt": "Time: {{time:whatever}}.",
    })
    assert r.status_code == 400
    assert "Unknown tag" in r.json()["detail"]


def test_create_prompt_accepts_valid_template(client) -> None:
    """A system prompt with valid template tags must be saved successfully."""
    r = client.post("/prompts", json={
        "slug": "valid-template-test",
        "name": "Valid",
        "system_prompt": "Now: {{time:current}}. Started: {{time:conversation-start}}.",
    })
    assert r.status_code == 201
    assert r.json()["slug"] == "valid-template-test"


# ── PUT /prompts/{slug} ────────────────────────────────────────────────────────


def test_update_prompt_rejects_bad_template(client) -> None:
    """PUT /prompts/{slug} with a malformed tag must be rejected with 400."""
    # Create a valid prompt first.
    client.post("/prompts", json={
        "slug": "update-bad-test",
        "name": "Original",
        "system_prompt": "No tags.",
    })

    r = client.put("/prompts/update-bad-test", json={
        "name": "Updated",
        "system_prompt": "Bad: {{time:nosuchname}}.",
    })
    assert r.status_code == 400
    assert "Unknown tag" in r.json()["detail"]


def test_update_prompt_accepts_valid_template(client) -> None:
    """PUT /prompts/{slug} with valid template tags must succeed."""
    client.post("/prompts", json={
        "slug": "update-valid-test",
        "name": "Original",
        "system_prompt": "No tags.",
    })

    r = client.put("/prompts/update-valid-test", json={
        "name": "Updated",
        "system_prompt": "Now it is {{time:current}}.",
    })
    assert r.status_code == 200
    assert "{{time:current}}" in r.json()["system_prompt"]
