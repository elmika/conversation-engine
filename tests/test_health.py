"""Health and middleware tests."""

from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    """GET /healthz returns status ok."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_accepts_request_id(client: TestClient) -> None:
    """X-Request-Id is accepted and does not change response."""
    response = client.get("/healthz", headers={"X-Request-Id": "test-req-123"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
