"""Application ports: abstract interfaces for infra adapters."""

from collections.abc import Iterable
from typing import Optional, Protocol, TypedDict
from types import TracebackType


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
    """Port for conversation and run persistence."""

    def get_messages(self, conversation_id: str) -> list[dict[str, str]]:
        """Return messages ordered by id (role, content)."""
        ...

    def append_message(self, conversation_id: str, role: str, content: str) -> int:
        """Append a message to the conversation and return its id."""
        ...

    def create_conversation(self) -> str:
        """Create a new conversation with a generated ID; return its id."""
        ...

    def create_conversation_with_id(self, conversation_id: str) -> None:
        """Create a new conversation with a specific ID (domain-generated)."""
        ...

    def record_run(
        self,
        conversation_id: str,
        assistant_message_id: int,
        prompt_slug: str,
        model: str,
        ttfb_ms: int,
        total_ms: int,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        finish_reason: Optional[str] = None,
    ) -> None:
        """Persist run metadata describing how an assistant message was generated."""
        ...


class UnitOfWork(Protocol):
    """
    Unit of Work pattern: manages transaction boundaries.
    
    The UoW owns the session lifecycle and controls commit/rollback.
    Repositories should only add/flush, never commit.
    
    Usage:
        with uow:
            uow.repo.create_conversation_with_id(cid)
            uow.repo.append_message(cid, "user", "Hello")
            # ... more operations ...
            uow.commit()  # Atomic commit of all operations
    """

    repo: ConversationRepo

    def commit(self) -> None:
        """Commit the current transaction."""
        ...

    def rollback(self) -> None:
        """Rollback the current transaction."""
        ...

    def __enter__(self) -> "UnitOfWork":
        """Enter context manager."""
        ...

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit context manager; rollback on exception."""
        ...