"""Tests for conversation repository (ordering, persistence, user scoping)."""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infra.persistence.db import Base
from app.infra.persistence.models import Conversation, Message, Run  # noqa: F401 - register models
from app.infra.persistence.repo_sqlalchemy import SQLAlchemyConversationRepo

TEST_USER = "test-user"


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
        cid = repo.create_conversation(user_id=TEST_USER)
        repo.append_message(cid, "user", "first")
        repo.append_message(cid, "assistant", "second")
        repo.append_message(cid, "user", "third")
        msgs = repo.get_messages(cid, TEST_USER)
        assert [m["content"] for m in msgs] == ["first", "second", "third"]
        assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    finally:
        session.close()


def test_get_conversation_created_at_returns_datetime() -> None:
    """get_conversation_created_at returns a datetime for an existing conversation."""
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        cid = repo.create_conversation(user_id=TEST_USER)
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


def test_get_active_conversation_returns_none_when_none() -> None:
    """get_active_conversation returns None when no open conversation exists for the user."""
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        result = repo.get_active_conversation(TEST_USER)
        assert result is None
    finally:
        session.close()


def test_get_active_conversation_returns_open_conversation() -> None:
    """get_active_conversation returns the ID of the open (ended_at IS NULL) conversation."""
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        cid = repo.create_conversation(user_id=TEST_USER)
        session.commit()
        result = repo.get_active_conversation(TEST_USER)
        assert result == cid
    finally:
        session.close()


def test_get_active_conversation_returns_none_after_ended() -> None:
    """get_active_conversation returns None after the conversation is ended."""
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        cid = repo.create_conversation(user_id=TEST_USER)
        session.commit()
        repo.end_conversation(cid, TEST_USER)
        session.commit()
        result = repo.get_active_conversation(TEST_USER)
        assert result is None
    finally:
        session.close()


def test_get_active_conversation_scoped_per_user() -> None:
    """Two users can each have a simultaneous active conversation."""
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        cid_a = repo.create_conversation(user_id="user-a")
        cid_b = repo.create_conversation(user_id="user-b")
        session.commit()

        assert repo.get_active_conversation("user-a") == cid_a
        assert repo.get_active_conversation("user-b") == cid_b
    finally:
        session.close()


def test_get_active_conversation_does_not_cross_users() -> None:
    """get_active_conversation('user-a') does not return user-b's active conversation."""
    session = _make_session()
    try:
        repo = SQLAlchemyConversationRepo(session)
        repo.create_conversation(user_id="user-b")
        session.commit()

        result = repo.get_active_conversation("user-a")
        assert result is None
    finally:
        session.close()
