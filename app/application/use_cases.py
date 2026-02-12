"""Chat use cases; depend only on ports and domain."""

import uuid
from typing import Callable, Optional

from app.application.ports import LLMResult
from app.domain.prompt_registry import get_prompt


def chat(
    messages: list[dict[str, str]],
    prompt_slug: Optional[str],
    default_slug: str,
    llm_complete: Callable[[str, list[dict[str, str]]], LLMResult],
    conversation_id: Optional[str] = None,
) -> tuple[str, str, str, int, int]:
    """
    Run non-streaming chat. No persistence yet (Day 4).

    Returns (conversation_id, assistant_message, model, ttfb_ms, total_ms).
    """
    cid = conversation_id or str(uuid.uuid4())
    slug = prompt_slug or default_slug
    spec = get_prompt(slug)
    instructions = spec["system_prompt"]
    result = llm_complete(instructions, messages)
    return (
        cid,
        result["text"],
        result["model"],
        result["ttfb_ms"],
        result["total_ms"],
    )
