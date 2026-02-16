"""Chat use cases; depend only on ports and domain."""

import uuid
from collections.abc import Iterable
from typing import Callable, Optional

from app.application.ports import LLMResult, StreamEvent
from app.domain.prompt_registry import get_prompt


def chat(
    messages: list[dict[str, str]],
    prompt_slug: Optional[str],
    default_slug: str,
    llm_complete: Callable[[str, list[dict[str, str]]], LLMResult],
    conversation_id: Optional[str] = None,
) -> tuple[str, str, str, int, int]:
    """Run non-streaming chat over the provided message history.

    `messages` should already contain any prior turns plus the new user message(s).
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


def stream_chat(
    messages: list[dict[str, str]],
    prompt_slug: Optional[str],
    default_slug: str,
    llm_stream: Callable[[str, list[dict[str, str]]], Iterable[StreamEvent]],
    conversation_id: Optional[str] = None,
) -> tuple[str, Iterable[StreamEvent]]:
    """
    Streaming chat over the provided message history; returns (conversation_id, streaming iterator).
    """
    cid = conversation_id or str(uuid.uuid4())
    slug = prompt_slug or default_slug
    spec = get_prompt(slug)
    instructions = spec["system_prompt"]
    events = llm_stream(instructions, messages)
    return cid, events
