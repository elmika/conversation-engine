"""Chat use cases; depend only on ports and domain."""

from collections.abc import Iterable
from typing import Callable, Optional, Union

from app.application.ports import LLMResult, StreamEvent
from app.domain.value_objects import ConversationId


def chat(
    messages: list[dict[str, str]],
    instructions: str,
    llm_complete: Callable[[str, list[dict[str, str]]], LLMResult],
    conversation_id: Optional[Union[str, ConversationId]] = None,
) -> tuple[str, str, str, int, int]:
    """Run non-streaming chat over the provided message history.

    `messages` should already contain any prior turns plus the new user message(s).
    Returns (conversation_id, assistant_message, model, ttfb_ms, total_ms).
    """
    cid = (
        ConversationId.from_string(conversation_id)
        if isinstance(conversation_id, str)
        else conversation_id or ConversationId.generate()
    )
    result = llm_complete(instructions, messages)
    return (
        str(cid),
        result["text"],
        result["model"],
        result["ttfb_ms"],
        result["total_ms"],
    )


def stream_chat(
    messages: list[dict[str, str]],
    instructions: str,
    llm_stream: Callable[[str, list[dict[str, str]]], Iterable[StreamEvent]],
    conversation_id: Optional[Union[str, ConversationId]] = None,
) -> tuple[str, Iterable[StreamEvent]]:
    """
    Streaming chat over the provided message history; returns (conversation_id, streaming iterator).
    """
    cid = (
        ConversationId.from_string(conversation_id)
        if isinstance(conversation_id, str)
        else conversation_id or ConversationId.generate()
    )
    events = llm_stream(instructions, messages)
    return str(cid), events
