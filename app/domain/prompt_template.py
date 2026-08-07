"""Prompt template rendering: replaces {{namespace:tag}} variables in system prompts."""

import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional

KNOWN_TAGS = {"time:current", "time:conversation-start", "time:lesson-time-spent"}
KNOWN_NAMESPACES = {"time"}
FILE_SECTION_TAGS = {"course", "user", "progress"}
TAG_PATTERN = re.compile(r"\{\{([^}]+)\}\}")


class PromptTemplateError(ValueError):
    """Raised when a prompt template contains an invalid or unknown tag."""


def _validate_tag(raw: str) -> None:
    """Validate a single tag string (contents between {{ and }}). Raises PromptTemplateError."""
    if ":" not in raw:
        if raw in FILE_SECTION_TAGS:
            return
        known_section = ", ".join(sorted(f"{{{{{t}}}}}" for t in FILE_SECTION_TAGS))
        raise PromptTemplateError(
            f"Malformed tag '{{{{{raw}}}}}': tags must use namespace:name format "
            f"or be one of: {known_section}"
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


def resolve_file_sections(
    template: str,
    loader: Callable[[str], Optional[str]],
) -> str:
    """Expand {{course}}, {{user}}, {{progress}} tags from file content.

    Time tags are left untouched for the second rendering pass.
    Raises PromptTemplateError if a file is not found.
    """
    def _replace(match: re.Match) -> str:
        raw = match.group(1)
        if raw not in FILE_SECTION_TAGS:
            return match.group(0)  # pass time tags through
        content = loader(raw)
        if content is None:
            raise PromptTemplateError(
                f"Section file not found: sections/{raw}/<user>.md"
            )
        return content

    return TAG_PATTERN.sub(_replace, template)


def render_instructions(
    instructions: str,
    resolve: Callable[[str], Optional[str]],
    conversation_start: Optional[datetime] = None,
) -> str:
    """Full two-pass render: file sections ({{course}}/{{user}}/{{progress}}) then {{time:*}}.

    `resolve` is a SlotResolver-shaped loader (tag -> file content or None).
    `conversation_start` anchors the {{time:*}} tags; defaults to now (elapsed = 0).
    """
    instructions = resolve_file_sections(instructions, resolve)

    now = datetime.now(timezone.utc)
    start = conversation_start or now
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    total_seconds = max(0, int((now - start).total_seconds()))
    minutes, secs = divmod(total_seconds, 60)
    if minutes == 0:
        time_spent = f"{secs} seconds"
    elif secs == 0:
        time_spent = f"{minutes} minutes"
    else:
        time_spent = f"{minutes} minutes {secs} seconds"

    context = {
        "time:current": now.strftime("%Y-%m-%d %H:%M UTC"),
        "time:conversation-start": start.strftime("%Y-%m-%d %H:%M UTC"),
        "time:lesson-time-spent": time_spent,
    }
    return render_prompt(instructions, context)


def render_prompt(template: str, context: dict[str, str]) -> str:
    """Replace known {{tags}} with context values; leave unrecognized patterns untouched.

    Validation of the original template happens at write time (validate_template).
    Injected slot content may contain arbitrary {{ }} syntax — it is never re-validated.
    """
    def _replace(match: re.Match) -> str:
        raw = match.group(1)
        if raw not in context:
            return match.group(0)
        return context[raw]

    return TAG_PATTERN.sub(_replace, template)
