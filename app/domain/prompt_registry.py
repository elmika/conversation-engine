"""Prompt governance: in-code registry keyed by prompt_slug."""

from typing import TypedDict, Union

from app.domain.value_objects import PromptSlug


class PromptSpec(TypedDict):
    """Name and system prompt for a registered prompt."""

    name: str
    system_prompt: str


PROMPTS: dict[str, PromptSpec] = {
    "default": {
        "name": "Default Assistant",
        "system_prompt": "You are a concise and precise assistant.",
    },
    "conflict-coach-v1": {
        "name": "Conflict Coach",
        "system_prompt": "You help users reason calmly through workplace conflicts.",
    },
}


def get_prompt(slug: Union[str, PromptSlug]) -> PromptSpec:
    """
    Return prompt spec for slug; fallback to default if unknown.
    
    Accepts either a string or PromptSlug value object.
    """
    slug_str = str(slug) if isinstance(slug, PromptSlug) else slug
    return PROMPTS.get(slug_str, PROMPTS["default"])


def validate_prompt_slug(slug: str) -> PromptSlug:
    """
    Validate and return a PromptSlug.
    
    Raises ValueError if slug is not in the registry.
    """
    return PromptSlug.from_string(slug, PROMPTS)


def get_prompt_slug_or_default(slug: Union[str, PromptSlug, None], default: str) -> PromptSlug:
    """
    Get a validated PromptSlug from an optional string, falling back to default.
    
    This encapsulates the common pattern of "use provided slug or fall back to default".
    """
    if isinstance(slug, PromptSlug):
        return slug
    return PromptSlug.from_string_or_default(slug, default, PROMPTS)
