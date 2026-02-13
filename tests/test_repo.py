"""Tests for conversation repository (ordering, persistence)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infra.persistence.db import Base
from app.infra.persistence.models import Conversation, Message, Run  # noqa: F401 - register models
from app.infra.persistence.repo_sqlalchemy import SQLAlchemyConversationRepo


def test_repo_get_messages_ordered_by_id() -> None:
    """get_messages returns messages in ORDER BY id ascending."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
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
