"""SQLAlchemy implementation of the PromptRepo port."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.persistence.models import Prompt


class SQLAlchemyPromptRepo:
    """Prompt persistence using SQLAlchemy Session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_prompt(self, slug: str) -> Optional[dict]:
        prompt = self._session.get(Prompt, slug)
        if prompt is None:
            return None
        return {"slug": prompt.slug, "name": prompt.name, "system_prompt": prompt.system_prompt}

    def get_prompt_or_default(self, slug: Optional[str], default_slug: str) -> dict:
        target = slug or default_slug
        result = self.get_prompt(target)
        if result is not None:
            return result
        if target != default_slug:
            result = self.get_prompt(default_slug)
            if result is not None:
                return result
        raise ValueError(f"Prompt '{target}' not found and default '{default_slug}' not found")

    def list_prompts(self) -> list[dict]:
        stmt = select(Prompt).order_by(Prompt.slug.asc())
        rows = self._session.execute(stmt).scalars().all()
        return [{"slug": p.slug, "name": p.name, "system_prompt": p.system_prompt} for p in rows]

    def upsert(self, slug: str, name: str, system_prompt: str) -> None:
        existing = self._session.get(Prompt, slug)
        if existing:
            existing.name = name
            existing.system_prompt = system_prompt
        else:
            self._session.add(Prompt(slug=slug, name=name, system_prompt=system_prompt))
