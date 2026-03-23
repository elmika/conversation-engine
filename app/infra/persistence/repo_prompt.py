"""SQLAlchemy implementation of the PromptRepo port."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.infra.persistence.models import Prompt, Run


class SQLAlchemyPromptRepo:
    """Prompt persistence using SQLAlchemy Session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_dict(self, prompt: Prompt) -> dict:
        return {
            "slug": prompt.slug,
            "name": prompt.name,
            "system_prompt": prompt.system_prompt,
            "model": prompt.model,
            "is_active": prompt.is_active,
        }

    def get_prompt(self, slug: str) -> Optional[dict]:
        prompt = self._session.get(Prompt, slug)
        if prompt is None:
            return None
        return self._to_dict(prompt)

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

    def list_prompts(self, include_disabled: bool = False) -> list[dict]:
        stmt = select(Prompt).order_by(Prompt.slug.asc())
        if not include_disabled:
            stmt = stmt.where(Prompt.is_active.is_(True))
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_dict(p) for p in rows]

    def upsert(self, slug: str, name: str, system_prompt: str, model: Optional[str] = None) -> None:
        existing = self._session.get(Prompt, slug)
        if existing:
            existing.name = name
            existing.system_prompt = system_prompt
            existing.model = model
        else:
            self._session.add(
                Prompt(slug=slug, name=name, system_prompt=system_prompt, model=model)
            )

    def create(self, slug: str, name: str, system_prompt: str, model: Optional[str] = None) -> None:
        """Insert a new prompt. Raises ValueError if slug already exists."""
        if self._session.get(Prompt, slug) is not None:
            raise ValueError(f"Prompt '{slug}' already exists")
        self._session.add(
            Prompt(slug=slug, name=name, system_prompt=system_prompt, model=model, is_active=True)
        )

    def update(self, slug: str, name: str, system_prompt: str, model: Optional[str] = None) -> bool:
        """Update an existing prompt. Returns False if not found."""
        existing = self._session.get(Prompt, slug)
        if existing is None:
            return False
        existing.name = name
        existing.system_prompt = system_prompt
        existing.model = model
        return True

    def set_active(self, slug: str, is_active: bool) -> bool:
        """Set is_active flag. Returns False if prompt not found."""
        existing = self._session.get(Prompt, slug)
        if existing is None:
            return False
        existing.is_active = is_active
        return True

    def delete(self, slug: str) -> bool:
        """Hard-delete a prompt row. Returns False if not found."""
        existing = self._session.get(Prompt, slug)
        if existing is None:
            return False
        self._session.delete(existing)
        return True

    def is_used_in_runs(self, slug: str) -> bool:
        """Return True if the slug appears in any run record."""
        stmt = select(Run).where(Run.prompt_slug == slug).limit(1)
        return self._session.execute(stmt).first() is not None
