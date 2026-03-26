"""Prompt template rendering: replaces {{namespace:tag}} variables in system prompts."""

import re
from typing import Optional

KNOWN_TAGS = {"time:current", "time:conversation-start", "time:lesson-time-spent"}
KNOWN_NAMESPACES = {"time"}
TAG_PATTERN = re.compile(r"\{\{([^}]+)\}\}")


class PromptTemplateError(ValueError):
    """Raised when a prompt template contains an invalid or unknown tag."""


def _validate_tag(raw: str) -> None:
    """Validate a single tag string (contents between {{ and }}). Raises PromptTemplateError."""
    if ":" not in raw:
        raise PromptTemplateError(
            f"Malformed tag '{{{{{raw}}}}}': tags must use namespace:name format"
        )
    namespace = raw.split(":", 1)[0]
    if namespace not in KNOWN_NAMESPACES:
        raise PromptTemplateError(
            f"Unknown namespace '{namespace}' in tag '{{{{{raw}}}}}'"
        )
    if raw not in KNOWN_TAGS:
        known = ", ".join(sorted(f"{{{{{t}}}}}" for t in KNOWN_TAGS))
        raise PromptTemplateError(
            f"Unknown tag '{{{{{raw}}}}}'. Known tags: {known}"
        )


def validate_template(template: str) -> None:
    """Scan for unknown or malformed tags. Raises PromptTemplateError on first bad tag."""
    for match in TAG_PATTERN.finditer(template):
        _validate_tag(match.group(1))


def render_prompt(template: str, context: dict[str, str]) -> str:
    """Replace {{tags}} with context values. Raises PromptTemplateError for bad tags."""
    def _replace(match: re.Match) -> str:
        raw = match.group(1)
        _validate_tag(raw)
        return context[raw]

    return TAG_PATTERN.sub(_replace, template)
