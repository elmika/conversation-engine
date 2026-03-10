"""Repo-level tests for list_conversations and get_messages_with_metadata."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infra.persistence.db import Base
from app.infra.persistence.models import Conversation, Message, Run  # noqa: F401
from app.infra.persistence.repo_sqlalchemy import SQLAlchemyConversationRepo


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session()


def test_list_conversations_empty() -> None:
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        rows, total = repo.list_conversations(page=1, page_size=20)
        assert rows == []
        assert total == 0
    finally:
        session.close()


def test_list_conversations_total_count() -> None:
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        for _ in range(5):
            repo.create_conversation()
        session.commit()
        rows, total = repo.list_conversations(page=1, page_size=20)
        assert total == 5
        assert len(rows) == 5
    finally:
        session.close()


def test_list_conversations_pagination() -> None:
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        for _ in range(7):
            repo.create_conversation()
        session.commit()
        rows_p1, total = repo.list_conversations(page=1, page_size=3)
        assert total == 7
        assert len(rows_p1) == 3

        rows_p2, total2 = repo.list_conversations(page=2, page_size=3)
        assert total2 == 7
        assert len(rows_p2) == 3

        rows_p3, total3 = repo.list_conversations(page=3, page_size=3)
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
        repo.create_conversation()
        session.commit()
        rows, _ = repo.list_conversations(page=1, page_size=20)
        assert "T" in rows[0]["created_at"]  # ISO 8601 format
    finally:
        session.close()


def test_get_messages_with_metadata() -> None:
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        cid = repo.create_conversation()
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
        cid = repo.create_conversation()
        session.commit()
        msgs = repo.get_messages_with_metadata(cid)
        assert msgs == []
    finally:
        session.close()
