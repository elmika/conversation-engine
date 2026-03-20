"""Static registry of supported OpenAI models."""

from __future__ import annotations

MODELS: dict[str, dict] = {
    "gpt-4.1-mini": {"name": "GPT-4.1 Mini"},
    "gpt-4o": {"name": "GPT-4o"},
    "gpt-4o-mini": {"name": "GPT-4o Mini"},
}


def list_models() -> list[dict]:
    """Return all models as [{slug, name}] ordered by slug."""
    return [{"slug": slug, **meta} for slug, meta in sorted(MODELS.items())]


def get_model(slug: str) -> dict:
    """Return model metadata for slug. Raises ValueError if unknown."""
    if slug not in MODELS:
        raise ValueError(f"Unknown model slug '{slug}'. Valid slugs: {sorted(MODELS)}")
    return {"slug": slug, **MODELS[slug]}


def validate_model_slug(slug: str) -> str:
    """Return slug if valid. Raises ValueError if unknown."""
    get_model(slug)
    return slug
