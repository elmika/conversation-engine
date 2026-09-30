"""Static registry of supported LLM models (OpenAI + Anthropic)."""

from __future__ import annotations

MODELS: dict[str, dict] = {
    "gpt-4.1": {
        "name": "GPT-4.1",
        "description": "Smartest non-reasoning model",
        "provider": "openai",
    },
    "gpt-5-mini": {
        "name": "GPT-5 mini",
        "description": "Near-frontier intelligence for cost sensitive, low latency, high volume workloads",
        "provider": "openai",
    },
    "gpt-5-nano": {
        "name": "GPT-5 nano",
        "description": "Fastest, most cost-efficient version of GPT-5",
        "provider": "openai",
    },
    "gpt-5.4-mini": {
        "name": "GPT-5.4 mini",
        "description": "Our strongest mini model yet for coding, computer use, and subagents",
        "provider": "openai",
    },
    "gpt-5.4-nano": {
        "name": "GPT-5.4 nano",
        "description": "Our cheapest GPT-5.4-class model for simple high-volume tasks",
        "provider": "openai",
    },

    "gpt-5.4-pro": {
        "name": "GPT-5.4 pro",
        "description": "Most capable GPT-5.4 model",
        "provider": "openai",
    },
    "gpt-5.6-luna": {
        "name": "GPT-5.6 Luna",
        "description": "High-volume/low-cost GPT-5.6 tier — under evaluation as a gpt-5.4-pro "
        "replacement for course-outline-proposal/wrap_up_model (docs/roadmap.md, untriaged)",
        "provider": "openai",
    },

    # --- Added 2026-09-17 during the model-tier review (docs/roadmap.md) — pulled
    # live from GET /v1/models + https://developers.openai.com/api/docs/pricing.
    "gpt-5.4": {
        "name": "GPT-5.4",
        "description": "Flagship GPT-5.4 model — more affordable than gpt-5.4-pro for coding "
        "and professional work",
        "provider": "openai",
    },
    "gpt-5.5": {
        "name": "GPT-5.5",
        "description": "Flagship model for the most complex professional work; successor tier "
        "to gpt-5.4",
        "provider": "openai",
    },
    "gpt-5.6-terra": {
        "name": "GPT-5.6 Terra",
        "description": "GPT-5.6 tier balancing intelligence and cost — roughly corresponds to "
        "the mini tier in earlier GPT-5 families",
        "provider": "openai",
    },
    "gpt-5.6-sol": {
        "name": "GPT-5.6 Sol",
        "description": "Flagship GPT-5.6 model — roughly corresponds to the unsuffixed tier in "
        "earlier GPT-5 families",
        "provider": "openai",
    },
    "gpt-6-astra": {
        "name": "GPT-6 Astra",
        "description": "Most capable current model, for the hardest end-to-end work — complex "
        "reasoning, coding, computer use, research",
        "provider": "openai",
    },

    # --- Expensive models: commented out to prevent accidental use during development ---
    # "gpt-5": {"name": "GPT-5", "description": "Reasoning model"},
    # "gpt-5-codex": {"name": "GPT-5 Codex", ...},
    # "gpt-5.1-codex": {"name": "GPT-5.1-codex", ...},
    # "gpt-5.1-codex-max": {"name": "GPT-5.1 Codex Max", ...},
    # "gpt-5.1-codex-mini": {"name": "GPT-5.1 Codex mini", ...},
    # "gpt-5.2-codex": {"name": "GPT-5.2 Codex", ...},
    # "gpt-5.3-codex": {"name": "GPT-5.3 Codex", ...},
    # "gpt-5.4": {"name": "GPT-5.4", ...},

    # --- Added 2026-09-28 to add Anthropic as a second LLM provider (see
    # app/infra/llm_anthropic.py, app/infra/llm_router.py). ---
    "claude-sonnet-5": {
        "name": "Claude Sonnet 5",
        "description": "Anthropic's balanced flagship model for everyday conversation and coding",
        "provider": "anthropic",
    },
    "claude-haiku-4-5": {
        "name": "Claude Haiku 4.5",
        "description": "Anthropic's fastest, most cost-efficient current model",
        "provider": "anthropic",
    },
    "claude-opus-5": {
        "name": "Claude Opus 5",
        "description": "Anthropic's most capable model for the hardest reasoning and agentic work",
        "provider": "anthropic",
    },

    # --- Added 2026-09-30 — newer generation released after the above entries
    # (opus-5.5: 2026-09-21, sonnet-5.5: 2026-09-28), confirmed live via
    # GET /v1/models. Note opus-5.5 is priced *below* opus-5 ($4/$20 vs
    # $5/$25 per app/domain/pricing.py), not a straight same-price successor.
    "claude-opus-5-5": {
        "name": "Claude Opus 5.5",
        "description": "Anthropic's latest model for long-running agentic coding and knowledge work",
        "provider": "anthropic",
    },
    "claude-sonnet-5-5": {
        "name": "Claude Sonnet 5.5",
        "description": "Anthropic's latest balanced model — speed and intelligence",
        "provider": "anthropic",
    },
}

# Display order — unpriced models (gpt-5-mini, gpt-5-nano) and the priciest
# tiers (e.g. claude-opus-5) are omitted from the learner-facing selector;
# their MODELS entries stay for reference and remain reachable via an
# explicit model_slug (admin/comparison tooling) but they're not offered by
# default.
_DISPLAY_ORDER = [
    "gpt-4.1",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "claude-sonnet-5",
    "claude-haiku-4-5",
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
