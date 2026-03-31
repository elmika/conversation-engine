"""Tests for conversation repository (ordering, persistence)."""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infra.persistence.db import Base
from app.infra.persistence.models import Conversation, Message, Run  # noqa: F401 - register models
from app.infra.persistence.repo_sqlalchemy import SQLAlchemyConversationRepo


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session()


def test_repo_get_messages_ordered_by_id() -> None:
    """get_messages returns messages in ORDER BY id ascending."""
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        cid = repo.create_conversation()
        repo.append_message(cid, "user", "first")
        repo.append_message(cid, "assistant", "second")
        repo.append_message(cid, "user", "third")
        msgs = repo.get_messages(cid)
        assert [m["content"] for m in msgs] == ["first", "second", "third"]
        assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    finally:
        session.close()


def test_get_conversation_created_at_returns_datetime() -> None:
    """get_conversation_created_at returns a datetime for an existing conversation."""
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        cid = repo.create_conversation()
        session.commit()
        result = repo.get_conversation_created_at(cid)
        assert result is not None
        assert isinstance(result, datetime)
    finally:
        session.close()


def test_get_conversation_created_at_returns_none_for_unknown() -> None:
    """get_conversation_created_at returns None for a conversation that does not exist."""
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        result = repo.get_conversation_created_at("nonexistent-id")
        assert result is None
    finally:
        session.close()
