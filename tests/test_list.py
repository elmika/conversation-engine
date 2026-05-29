"""Repo-level tests for list_conversations and get_messages_with_metadata."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infra.persistence.db import Base
from app.infra.persistence.models import Conversation, Message, Run  # noqa: F401
from app.infra.persistence.repo_sqlalchemy import SQLAlchemyConversationRepo

TEST_USER = "test-user"


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session()


def test_list_conversations_empty() -> None:
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        rows, total = repo.list_conversations(TEST_USER, page=1, page_size=20)
        assert rows == []
        assert total == 0
    finally:
        session.close()


def test_list_conversations_total_count() -> None:
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        for _ in range(5):
            repo.create_conversation(user_id=TEST_USER)
        session.commit()
        rows, total = repo.list_conversations(TEST_USER, page=1, page_size=20)
        assert total == 5
        assert len(rows) == 5
    finally:
        session.close()


def test_list_conversations_pagination() -> None:
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        for _ in range(7):
            repo.create_conversation(user_id=TEST_USER)
        session.commit()
        rows_p1, total = repo.list_conversations(TEST_USER, page=1, page_size=3)
        assert total == 7
        assert len(rows_p1) == 3

        rows_p2, total2 = repo.list_conversations(TEST_USER, page=2, page_size=3)
        assert total2 == 7
        assert len(rows_p2) == 3

        rows_p3, total3 = repo.list_conversations(TEST_USER, page=3, page_size=3)
        assert total3 == 7
        assert len(rows_p3) == 1

        # All IDs are distinct
        all_ids = [r["id"] for r in rows_p1 + rows_p2 + rows_p3]
        assert len(set(all_ids)) == 7
    finally:
        session.close()


def test_list_conversations_has_iso_created_at() -> None:
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        repo.create_conversation(user_id=TEST_USER)
        session.commit()
        rows, _ = repo.list_conversations(TEST_USER, page=1, page_size=20)
        assert "T" in rows[0]["created_at"]  # ISO 8601 format
    finally:
        session.close()


def test_list_conversations_scoped_to_user() -> None:
    """Each user sees only their own conversations."""
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        for _ in range(3):
            repo.create_conversation(user_id="user-a")
        for _ in range(2):
            repo.create_conversation(user_id="user-b")
        session.commit()

        rows_a, total_a = repo.list_conversations("user-a", page=1, page_size=20)
        rows_b, total_b = repo.list_conversations("user-b", page=1, page_size=20)

        assert total_a == 3
        assert len(rows_a) == 3
        assert total_b == 2
        assert len(rows_b) == 2

        ids_a = {r["id"] for r in rows_a}
        ids_b = {r["id"] for r in rows_b}
        assert ids_a.isdisjoint(ids_b), "user-a and user-b share conversation IDs"
    finally:
        session.close()


def test_list_conversations_user_a_does_not_see_user_b() -> None:
    """list_conversations('user-a') never returns user-b's conversations."""
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        repo.create_conversation(user_id="user-b")
        session.commit()

        rows_a, total_a = repo.list_conversations("user-a", page=1, page_size=20)
        assert rows_a == []
        assert total_a == 0
    finally:
        session.close()


def test_get_messages_with_metadata() -> None:
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        cid = repo.create_conversation(user_id=TEST_USER)
        repo.append_message(cid, "user", "Hello")
        repo.append_message(cid, "assistant", "Hi there")
        session.commit()

        msgs = repo.get_messages_with_metadata(cid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"
        assert "id" in msgs[0]
        assert "created_at" in msgs[0]
        assert "T" in msgs[0]["created_at"]
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "Hi there"
        # Ordered by id ASC
        assert msgs[0]["id"] < msgs[1]["id"]
    finally:
        session.close()


def test_get_messages_with_metadata_empty() -> None:
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        cid = repo.create_conversation(user_id=TEST_USER)
        session.commit()
        msgs = repo.get_messages_with_metadata(cid)
        assert msgs == []
    finally:
        session.close()
