"""Tests for prompt_seeder."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infra.persistence.db import Base
from app.infra.persistence.models import Prompt  # noqa: F401 - register model
from app.infra.persistence.repo_prompt import SQLAlchemyPromptRepo
from app.infra.prompt_seeder import seed_prompts_from_directory


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.close()


def test_seeds_valid_md_files(tmp_path, session) -> None:
    (tmp_path / "default.md").write_text("---\nname: Default\n---\nYou are helpful.")
    (tmp_path / "coach.md").write_text("---\nname: Coach\n---\nYou are a coach.")

    seed_prompts_from_directory(tmp_path, session)

    repo = SQLAlchemyPromptRepo(session)
    rows = repo.list_prompts()
    slugs = [r["slug"] for r in rows]
    assert "default" in slugs
    assert "coach" in slugs
    assert repo.get_prompt("default")["system_prompt"] == "You are helpful."


def test_skips_missing_directory(tmp_path, session) -> None:
    missing = tmp_path / "nonexistent"
    seed_prompts_from_directory(missing, session)  # should not raise

    repo = SQLAlchemyPromptRepo(session)
    assert repo.list_prompts() == []


def test_skips_file_with_no_frontmatter(tmp_path, session) -> None:
    (tmp_path / "bad.md").write_text("No frontmatter here.")
    (tmp_path / "good.md").write_text("---\nname: Good\n---\nGood prompt.")

    seed_prompts_from_directory(tmp_path, session)

    repo = SQLAlchemyPromptRepo(session)
    rows = repo.list_prompts()
    assert len(rows) == 1
    assert rows[0]["slug"] == "good"


def test_skips_file_with_missing_name(tmp_path, session) -> None:
    (tmp_path / "noname.md").write_text("---\ntitle: Something\n---\nA prompt.")

    seed_prompts_from_directory(tmp_path, session)

    repo = SQLAlchemyPromptRepo(session)
    assert repo.list_prompts() == []


def test_upserts_on_second_run(tmp_path, session) -> None:
    md = tmp_path / "default.md"
    md.write_text("---\nname: Old Name\n---\nOld prompt.")
    seed_prompts_from_directory(tmp_path, session)

    md.write_text("---\nname: New Name\n---\nNew prompt.")
    seed_prompts_from_directory(tmp_path, session)

    repo = SQLAlchemyPromptRepo(session)
    result = repo.get_prompt("default")
    assert result["name"] == "New Name"
    assert result["system_prompt"] == "New prompt."
