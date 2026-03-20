"""Seed prompts from .md files in a directory into the database."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.model_registry import validate_model_slug
from app.infra.persistence.repo_prompt import SQLAlchemyPromptRepo

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _parse_md(content: str) -> tuple[dict[str, str], str] | None:
    """Parse YAML frontmatter and body from a markdown string. Returns (meta, body) or None."""
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return None
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, m.group(2).strip()


def seed_prompts_from_directory(directory: Path, session: Session) -> None:
    """Upsert all *.md prompts from directory into the DB, then commit."""
    if not directory.exists():
        logger.debug("Prompts directory %s not found; skipping seed", directory)
        return

    repo = SQLAlchemyPromptRepo(session)
    seeded = 0

    for path in sorted(directory.glob("*.md")):
        slug = path.stem
        content = path.read_text(encoding="utf-8")
        parsed = _parse_md(content)
        if parsed is None:
            logger.warning("Skipping %s: missing or invalid frontmatter", path.name)
            continue
        meta, system_prompt = parsed
        name = meta.get("name")
        if not name:
            logger.warning("Skipping %s: 'name' field missing in frontmatter", path.name)
            continue
        if not system_prompt:
            logger.warning("Skipping %s: body (system_prompt) is empty", path.name)
            continue
        model: str | None = None
        raw_model = meta.get("model")
        if raw_model:
            try:
                model = validate_model_slug(raw_model)
            except ValueError as exc:
                logger.error("Skipping %s: invalid model slug — %s", path.name, exc)
                continue
        repo.upsert(slug=slug, name=name, system_prompt=system_prompt, model=model)
        seeded += 1
        logger.debug("Seeded prompt '%s' (%s)", slug, name)

    session.commit()
    logger.info("Seeded %d prompt(s) from %s", seeded, directory)
