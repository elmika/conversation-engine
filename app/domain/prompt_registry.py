"""Prompt governance: in-code registry keyed by prompt_slug."""

from typing import TypedDict


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


def get_prompt(slug: str) -> PromptSpec:
    """Return prompt spec for slug; fallback to default if unknown."""
    return PROMPTS.get(slug, PROMPTS["default"])
