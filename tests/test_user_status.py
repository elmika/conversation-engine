"""Tests for GET /u/{user_id}/status endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app as main_app
from tests.conftest import TEST_USER


@pytest.fixture
def client():
    return TestClient(main_app)


@pytest.fixture
def client_with_sections(tmp_path):
    """Test client with a temp sections_dir."""
    from app.api import routes as api_routes
    from app.settings import Settings

    def _override_settings():
        s = Settings()
        s.sections_dir = str(tmp_path)
        return s

    main_app.dependency_overrides[api_routes.get_settings] = _override_settings
    with TestClient(main_app) as c:
        yield c, tmp_path
    main_app.dependency_overrides.clear()


def test_status_no_profile(client_with_sections) -> None:
    """GET /u/{user_id}/status returns has_profile=false when no user file exists."""
    client, sections_dir = client_with_sections
    (sections_dir / "user").mkdir()
    # No <user_id>.md written

    r = client.get(f"/u/{TEST_USER}/status")
    assert r.status_code == 200
    assert r.json() == {"has_profile": False}


def test_status_has_profile(client_with_sections) -> None:
    """GET /u/{user_id}/status returns has_profile=true when user file exists."""
    client, sections_dir = client_with_sections
    (sections_dir / "user").mkdir()
    (sections_dir / "user" / f"{TEST_USER}.md").write_text("# User Profile")

    r = client.get(f"/u/{TEST_USER}/status")
    assert r.status_code == 200
    assert r.json() == {"has_profile": True}


def test_status_different_users_independent(client_with_sections) -> None:
    """Profile existence is scoped per user_id."""
    client, sections_dir = client_with_sections
    (sections_dir / "user").mkdir()
    (sections_dir / "user" / "user-with-profile.md").write_text("# Profile")

    r_with = client.get("/u/user-with-profile/status")
    assert r_with.json() == {"has_profile": True}

    r_without = client.get("/u/user-without-profile/status")
    assert r_without.json() == {"has_profile": False}
