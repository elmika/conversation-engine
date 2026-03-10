"""Tests for SQLAlchemyPromptRepo."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infra.persistence.db import Base
from app.infra.persistence.models import Prompt  # noqa: F401 - register model
from app.infra.persistence.repo_prompt import SQLAlchemyPromptRepo


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


def test_upsert_and_get_prompt(session) -> None:
    repo = SQLAlchemyPromptRepo(session)
    repo.upsert("default", "Default Assistant", "You are helpful.")
    session.commit()

    result = repo.get_prompt("default")
    assert result == {"slug": "default", "name": "Default Assistant", "system_prompt": "You are helpful."}


def test_get_prompt_returns_none_for_unknown(session) -> None:
    repo = SQLAlchemyPromptRepo(session)
    assert repo.get_prompt("nonexistent") is None


def test_upsert_updates_existing(session) -> None:
    repo = SQLAlchemyPromptRepo(session)
    repo.upsert("default", "Old Name", "Old prompt")
    session.commit()
    repo.upsert("default", "New Name", "New prompt")
    session.commit()

    result = repo.get_prompt("default")
    assert result["name"] == "New Name"
    assert result["system_prompt"] == "New prompt"


def test_list_prompts_ordered_by_slug(session) -> None:
    repo = SQLAlchemyPromptRepo(session)
    repo.upsert("zzz", "Z Prompt", "z")
    repo.upsert("aaa", "A Prompt", "a")
    repo.upsert("mmm", "M Prompt", "m")
    session.commit()

    rows = repo.list_prompts()
    assert [r["slug"] for r in rows] == ["aaa", "mmm", "zzz"]


def test_get_prompt_or_default_uses_slug(session) -> None:
    repo = SQLAlchemyPromptRepo(session)
    repo.upsert("default", "Default", "default prompt")
    repo.upsert("coach", "Coach", "coaching prompt")
    session.commit()

    result = repo.get_prompt_or_default("coach", "default")
    assert result["slug"] == "coach"


def test_get_prompt_or_default_falls_back(session) -> None:
    repo = SQLAlchemyPromptRepo(session)
    repo.upsert("default", "Default", "default prompt")
    session.commit()

    result = repo.get_prompt_or_default(None, "default")
    assert result["slug"] == "default"


def test_get_prompt_or_default_raises_if_neither_found(session) -> None:
    repo = SQLAlchemyPromptRepo(session)

    with pytest.raises(ValueError, match="not found"):
        repo.get_prompt_or_default("missing", "also-missing")
