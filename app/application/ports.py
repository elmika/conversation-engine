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

    # "delta" for incremental text, "final" for completion metadata, "error" for failures.
    type: str
    # Present when type == "delta".
    delta: str
    # Present when type == "final".
    text: str
    model: str
    ttfb_ms: int
    total_ms: int
    # Present when type == "error".
    error_type: str  # e.g., "rate_limit", "timeout", "api_error"
    error_message: str  # Human-readable error description


class LLMPort(Protocol):
    """Port for LLM calls (OpenAI Responses API)."""

    def complete(
        self,
        instructions: str,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ) -> LLMResult:
        """Run non-streaming completion; return assistant text, model, timings.

        If model is provided it overrides the adapter's default model.
        """
        ...

    def stream(
        self,
        instructions: str,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ) -> Iterable[StreamEvent]:
        """Run streaming completion; yield StreamEvent items.

        If model is provided it overrides the adapter's default model.
        """
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

    def list_conversations(self, page: int, page_size: int) -> tuple[list[dict], int]:
        """Return (rows, total) ordered by created_at DESC with pagination."""
        ...

    def get_messages_with_metadata(self, conversation_id: str) -> list[dict]:
        """Return [{id, role, content, created_at}] ordered by id ASC."""
        ...

    def rename_conversation(self, conversation_id: str, name: str) -> None:
        """Set the display name for a conversation."""
        ...

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all its messages and runs."""
        ...

    def truncate_from(self, conversation_id: str, message_id: int) -> None:
        """Delete messages with id >= message_id and their associated runs."""
        ...


class PromptRepo(Protocol):
    """Port for prompt persistence."""

    def get_prompt(self, slug: str) -> Optional[dict]:
        """Return prompt dict {slug, name, system_prompt, model} or None if not found."""
        ...

    def get_prompt_or_default(self, slug: Optional[str], default_slug: str) -> dict:
        """Return prompt for slug, falling back to default_slug. Raises ValueError if neither found.

        Returned dict includes {slug, name, system_prompt, model} where model may be None.
        """
        ...

    def list_prompts(self, include_disabled: bool = False) -> list[dict]:
        """Return prompts as [{slug, name, system_prompt, model, is_active}] ordered by slug.

        When include_disabled=False (default), only active prompts are returned.
        """
        ...

    def upsert(self, slug: str, name: str, system_prompt: str, model: Optional[str] = None) -> None:
        """Insert or update a prompt by slug. model is the preferred model slug (or None)."""
        ...

    def create(self, slug: str, name: str, system_prompt: str, model: Optional[str] = None) -> None:
        """Insert a new prompt. Raises ValueError if slug already exists."""
        ...

    def update(self, slug: str, name: str, system_prompt: str, model: Optional[str] = None) -> bool:
        """Update an existing prompt. Returns False if not found."""
        ...

    def set_active(self, slug: str, is_active: bool) -> bool:
        """Set is_active flag. Returns False if prompt not found."""
        ...

    def delete(self, slug: str) -> bool:
        """Hard-delete a prompt row. Returns False if not found."""
        ...

    def is_used_in_runs(self, slug: str) -> bool:
        """Return True if the slug appears in any run record."""
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