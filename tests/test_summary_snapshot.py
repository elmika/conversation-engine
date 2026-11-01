"""A session summary is frozen when the session ends, not rebuilt from today's files."""

import pytest
from fastapi.testclient import TestClient

from app.learning.summary_snapshot import load_summary_snapshot, save_summary_snapshot
from app.main import app as main_app
from tests.conftest import TEST_USER


@pytest.fixture
def client_with_sections(tmp_path):
    from app.api import routes as api_routes
    from app.settings import Settings

    def _override_settings():
        s = Settings()
        s.sections_dir = str(tmp_path)
        return s

    main_app.dependency_overrides[api_routes.get_settings] = _override_settings
    with TestClient(main_app) as c:
        yield c, tmp_path
    main_app.dependency_overrides.pop(api_routes.get_settings, None)


def _write_course(sections_dir, title: str) -> None:
    (sections_dir / "course").mkdir(exist_ok=True)
    (sections_dir / "course" / f"{TEST_USER}.md").write_text(
        f"# Course: {title}\n\n## Modules\n\n1. First module\n", encoding="utf-8"
    )


def _start_conversation(client) -> str:
    r = client.post(
        f"/u/{TEST_USER}/conversations", json={"messages": [{"role": "user", "content": "Hi"}]}
    )
    assert r.status_code == 200
    return r.json()["conversation_id"]


def test_past_session_keeps_its_own_summary(client_with_sections) -> None:
    client, sections_dir = client_with_sections
    _write_course(sections_dir, "Pandas")
    first = _start_conversation(client)
    assert client.post(f"/u/{TEST_USER}/conversations/{first}/end-session").status_code == 200

    # A new setup later replaces the learner's course file.
    _write_course(sections_dir, "Public speaking")

    r = client.get(f"/u/{TEST_USER}/conversations/{first}/summary")
    assert r.status_code == 200
    assert r.json()["course_name"] == "Pandas"


def test_ended_conversation_without_snapshot_has_no_summary(client_with_sections) -> None:
    """Setup conversations, or ones ended before snapshots: 404, never today's state."""
    client, sections_dir = client_with_sections
    _write_course(sections_dir, "Pandas")
    cid = _start_conversation(client)
    client.post(f"/u/{TEST_USER}/conversations/{cid}/end-session")
    (sections_dir / "summaries" / TEST_USER / f"{cid}.json").unlink()

    r = client.get(f"/u/{TEST_USER}/conversations/{cid}/summary")
    assert r.status_code == 404


def test_snapshot_round_trip(tmp_path) -> None:
    summary = {"course_name": "Pandas", "modules": [], "next_step": None}
    save_summary_snapshot(str(tmp_path), "user-1", "conv-1", summary)
    assert load_summary_snapshot(str(tmp_path), "user-1", "conv-1") == summary
    assert load_summary_snapshot(str(tmp_path), "user-1", "conv-2") is None


@pytest.mark.parametrize(("user_id", "conversation_id"), [("..", "c"), ("u", "../x"), ("u/v", "c")])
def test_snapshot_refuses_ids_that_leave_the_directory(tmp_path, user_id, conversation_id) -> None:
    with pytest.raises(ValueError):
        load_summary_snapshot(str(tmp_path), user_id, conversation_id)
