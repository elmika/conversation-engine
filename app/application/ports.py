"""Application ports: abstract interfaces for infra adapters."""

from typing import Iterable, Protocol, TypedDict


class Timings(TypedDict):
    """TTFB and total latency in ms."""

    ttfb_ms: int
    total_ms: int


class LLMResult(TypedDict):
    """Result of a single non-streaming LLM call."""

    text: str
    model: str
    ttfb_ms: int
    total_ms: int


class StreamEvent(TypedDict, total=False):
    """Event from a streaming LLM call."""

    # "delta" for incremental text, "final" for completion metadata.
    type: str
    # Present when type == "delta".
    delta: str
    # Present when type == "final".
    text: str
    model: str
    ttfb_ms: int
    total_ms: int


class LLMPort(Protocol):
    """Port for LLM calls (OpenAI Responses API)."""

    def complete(self, instructions: str, messages: list[dict[str, str]]) -> LLMResult:
        """Run non-streaming completion; return assistant text, model, timings."""
        ...

    def stream(self, instructions: str, messages: list[dict[str, str]]) -> Iterable[StreamEvent]:
        """Run streaming completion; yield StreamEvent items."""
        ...


class ConversationRepo(Protocol):
    """Port for conversation persistence. Implemented in Day 4."""

    def get_messages(self, conversation_id: str) -> list[dict[str, str]]:
        """Return messages ordered by id (role, content)."""
        ...

    def append_message(self, conversation_id: str, role: str, content: str) -> None:
        """Append a message to the conversation."""
        ...

    def create_conversation(self) -> str:
        """Create a new conversation; return its id."""
        ...