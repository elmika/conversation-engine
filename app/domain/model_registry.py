"""Static registry of supported OpenAI models."""

from __future__ import annotations

MODELS: dict[str, dict] = {
    "gpt-4.1": {
        "name": "GPT-4.1",
        "description": "Smartest non-reasoning model",
    },
    "gpt-5": {
        "name": "GPT-5",
        "description": "Previous intelligent reasoning model for coding and agentic tasks with configurable reasoning effort",
    },
    "gpt-5-mini": {
        "name": "GPT-5 mini",
        "description": "Near-frontier intelligence for cost sensitive, low latency, high volume workloads",
    },
    "gpt-5-nano": {
        "name": "GPT-5 nano",
        "description": "Fastest, most cost-efficient version of GPT-5",
    },
    "gpt-5-codex": {
        "name": "GPT-5 Codex",
        "description": "A version of GPT-5 optimized for agentic coding in Codex",
    },
    "gpt-5.1-codex": {
        "name": "GPT-5.1 Codex",
        "description": "A version of GPT-5.1 optimized for agentic coding in Codex",
    },
    "gpt-5.1-codex-max": {
        "name": "GPT-5.1 Codex Max",
        "description": "A version of GPT-5.1-codex optimized for long running tasks",
    },
    "gpt-5.1-codex-mini": {
        "name": "GPT-5.1 Codex mini",
        "description": "Smaller, more cost-effective, less-capable version of GPT-5.1-Codex",
    },
    "gpt-5.2-codex": {
        "name": "GPT-5.2 Codex",
        "description": "Our most intelligent coding model optimized for long-horizon, agentic coding tasks",
    },
    "gpt-5.3-codex": {
        "name": "GPT-5.3 Codex",
        "description": "The most capable agentic coding model to date",
    },
    "gpt-5.4": {
        "name": "GPT-5.4",
        "description": "Best intelligence at scale for agentic, coding, and professional workflows",
    },
    "gpt-5.4-pro": {
        "name": "GPT-5.4 pro",
        "description": "Version of GPT-5.4 that produces smarter and more precise responses",
    },
    "gpt-5.4-mini": {
        "name": "GPT-5.4 mini",
        "description": "Our strongest mini model yet for coding, computer use, and subagents",
    },
    "gpt-5.4-nano": {
        "name": "GPT-5.4 nano",
        "description": "Our cheapest GPT-5.4-class model for simple high-volume tasks",
    },
}

# Display order (as specified)
_DISPLAY_ORDER = [
    "gpt-4.1",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5-codex",
    "gpt-5.1-codex",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex-mini",
    "gpt-5.2-codex",
    "gpt-5.3-codex",
    "gpt-5.4",
    "gpt-5.4-pro",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
]


def list_models() -> list[dict]:
    """Return all models as [{slug, name, description}] in display order."""
    return [{"slug": slug, **MODELS[slug]} for slug in _DISPLAY_ORDER]


def get_model(slug: str) -> dict:
    """Return model metadata for slug. Raises ValueError if unknown."""
    if slug not in MODELS:
        raise ValueError(f"Unknown model slug '{slug}'. Valid slugs: {sorted(MODELS)}")
    return {"slug": slug, **MODELS[slug]}


def validate_model_slug(slug: str) -> str:
    """Return slug if valid. Raises ValueError if unknown."""
    get_model(slug)
    return slug
