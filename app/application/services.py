"""Application services: orchestrate use cases + persistence."""

from collections.abc import Callable, Iterable
from typing import Optional

from app.application.ports import LLMPort, LLMResult, PromptRepo, StreamEvent, UnitOfWork
from app.application.use_cases import chat, stream_chat
from app.domain.history import trim_history
from app.domain.value_objects import ConversationId


class ConversationService:
    """
    Service layer for conversation workflows.

    Orchestrates: load history → trim history → call LLM → persist → return result.
    Each service method defines a transaction boundary using UnitOfWork.
    Routes become thin glue that validates input and formats HTTP/SSE responses.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        llm: LLMPort,
        prompt_repo: PromptRepo,
        default_prompt_slug: str,
        max_history_turns: Optional[int] = None,
        max_history_tokens: Optional[int] = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._prompt_repo = prompt_repo
        self._default_prompt_slug = default_prompt_slug
        self._max_history_turns = max_history_turns
        self._max_history_tokens = max_history_tokens

    def _resolve_prompt(self, slug: Optional[str]) -> tuple[str, str]:
        """Resolve prompt slug to (used_slug, system_prompt). Falls back to default."""
        record = self._prompt_repo.get_prompt_or_default(slug, self._default_prompt_slug)
        return record["slug"], record["system_prompt"]

    def create_and_chat(
        self,
        messages: list[dict[str, str]],
        prompt_slug: Optional[str] = None,
    ) -> tuple[str, str, str, int, int]:
        """
        Create a new conversation and run the first turn (non-streaming).

        Transaction boundary: all operations commit atomically.
        Returns: (conversation_id, assistant_message, model, ttfb_ms, total_ms)
        """
        used_prompt_slug, instructions = self._resolve_prompt(prompt_slug)

        # Create conversation with domain-generated ID
        conv_id = ConversationId.generate()
        cid_str = str(conv_id)

        with self._uow_factory() as uow:
            # Persist conversation and user messages
            uow.repo.create_conversation_with_id(cid_str)
            first_user = next((m for m in messages if m["role"] == "user"), None)
            if first_user:
                uow.repo.rename_conversation(cid_str, first_user["content"][:60].strip())
            for msg in messages:
                uow.repo.append_message(cid_str, msg["role"], msg["content"])

            # Call LLM
            conversation_id, assistant_message, model, ttfb_ms, total_ms = chat(
                messages=messages,
                instructions=instructions,
                llm_complete=self._llm.complete,
                conversation_id=conv_id,
            )

            # Persist assistant message and run metadata
            assistant_message_id = uow.repo.append_message(
                conversation_id, "assistant", assistant_message
            )
            uow.repo.record_run(
                conversation_id=conversation_id,
                assistant_message_id=assistant_message_id,
                prompt_slug=used_prompt_slug,
                model=model,
                ttfb_ms=ttfb_ms,
                total_ms=total_ms,
            )

            # Atomic commit of all operations
            uow.commit()

        return conversation_id, assistant_message, model, ttfb_ms, total_ms

    def append_and_chat(
        self,
        conversation_id: str,
        messages: list[dict[str, str]],
        prompt_slug: Optional[str] = None,
    ) -> tuple[str, str, str, int, int]:
        """
        Append a new turn to an existing conversation (non-streaming).

        Transaction boundary: all operations commit atomically.
        Loads history, trims to limits, combines with new messages, calls LLM, persists response.
        Returns: (conversation_id, assistant_message, model, ttfb_ms, total_ms)
        Raises: ValueError if conversation not found.
        """
        used_prompt_slug, instructions = self._resolve_prompt(prompt_slug)

        with self._uow_factory() as uow:
            # Load conversation history
            history = uow.repo.get_messages(conversation_id)
            if not history:
                raise ValueError(f"Conversation {conversation_id} not found")

            # Persist user messages for this turn
            for msg in messages:
                uow.repo.append_message(conversation_id, msg["role"], msg["content"])

            # Trim history to stay within limits (prevents context overflow)
            trim_result = trim_history(
                history,
                max_turns=self._max_history_turns,
                max_tokens=self._max_history_tokens,
                conversation_id=conversation_id,
            )

            # Combine trimmed history with new messages
            combined_messages = trim_result["messages"] + messages

            # Call LLM with trimmed history
            conv_id, assistant_message, model, ttfb_ms, total_ms = chat(
                messages=combined_messages,
                instructions=instructions,
                llm_complete=self._llm.complete,
                conversation_id=conversation_id,
            )

            # Persist assistant message and run metadata
            assistant_message_id = uow.repo.append_message(
                conv_id, "assistant", assistant_message
            )
            uow.repo.record_run(
                conversation_id=conv_id,
                assistant_message_id=assistant_message_id,
                prompt_slug=used_prompt_slug,
                model=model,
                ttfb_ms=ttfb_ms,
                total_ms=total_ms,
            )

            # Atomic commit of all operations
            uow.commit()

        return conv_id, assistant_message, model, ttfb_ms, total_ms

    def create_and_stream(
        self,
        messages: list[dict[str, str]],
        prompt_slug: Optional[str] = None,
    ) -> tuple[str, Iterable[StreamEvent], str, UnitOfWork]:
        """
        Create a new conversation and stream the first turn.

        Transaction boundary: conversation + user messages are committed immediately.
        The UoW is returned for the caller to persist the final assistant message + run.

        Returns: (conversation_id, event_iterator, used_prompt_slug, uow)
        """
        used_prompt_slug, instructions = self._resolve_prompt(prompt_slug)
        conv_id = ConversationId.generate()
        cid_str = str(conv_id)

        # Create a UoW for the initial setup (conversation + user messages)
        uow_setup = self._uow_factory()
        with uow_setup:
            uow_setup.repo.create_conversation_with_id(cid_str)
            first_user = next((m for m in messages if m["role"] == "user"), None)
            if first_user:
                uow_setup.repo.rename_conversation(cid_str, first_user["content"][:60].strip())
            for msg in messages:
                uow_setup.repo.append_message(cid_str, msg["role"], msg["content"])
            uow_setup.commit()

        # Start streaming
        conversation_id, events = stream_chat(
            messages=messages,
            instructions=instructions,
            llm_stream=self._llm.stream,
            conversation_id=conv_id,
        )

        # Return a new UoW for the caller to persist the final result
        uow_final = self._uow_factory()
        return conversation_id, events, used_prompt_slug, uow_final

    def append_and_stream(
        self,
        conversation_id: str,
        messages: list[dict[str, str]],
        prompt_slug: Optional[str] = None,
    ) -> tuple[str, Iterable[StreamEvent], str, UnitOfWork]:
        """
        Append a new turn to an existing conversation with streaming.

        Transaction boundary: user messages are committed immediately.
        The UoW is returned for the caller to persist the final assistant message + run.

        Loads history, trims to limits, combines with new messages, starts streaming.
        Returns: (conversation_id, event_iterator, used_prompt_slug, uow)
        Raises: ValueError if conversation not found.
        """
        used_prompt_slug, instructions = self._resolve_prompt(prompt_slug)

        # Load history and persist user messages in one transaction
        uow_setup = self._uow_factory()
        with uow_setup:
            history = uow_setup.repo.get_messages(conversation_id)
            if not history:
                raise ValueError(f"Conversation {conversation_id} not found")

            for msg in messages:
                uow_setup.repo.append_message(conversation_id, msg["role"], msg["content"])
            uow_setup.commit()

        # Trim history to stay within limits (prevents context overflow)
        trim_result = trim_history(
            history,
            max_turns=self._max_history_turns,
            max_tokens=self._max_history_tokens,
            conversation_id=conversation_id,
        )

        # Combine trimmed history with new messages
        combined_messages = trim_result["messages"] + messages

        # Start streaming with full history
        conv_id, events = stream_chat(
            messages=combined_messages,
            instructions=instructions,
            llm_stream=self._llm.stream,
            conversation_id=conversation_id,
        )

        # Return a new UoW for the caller to persist the final result
        uow_final = self._uow_factory()
        return conv_id, events, used_prompt_slug, uow_final

    def rewind_and_stream(
        self,
        conversation_id: str,
        message_id: int,
        new_content: str,
        prompt_slug: Optional[str] = None,
    ) -> tuple[str, Iterable[StreamEvent], str, UnitOfWork]:
        """
        Rewind a conversation to message_id, replace it with new_content, and stream.

        Deletes message_id and everything after it, appends new_content as a user
        message, then streams the assistant's response using the retained history.

        Returns: (conversation_id, event_iterator, used_prompt_slug, uow)
        Raises: ValueError if conversation not found.
        """
        used_prompt_slug, instructions = self._resolve_prompt(prompt_slug)

        uow_setup = self._uow_factory()
        with uow_setup:
            history = uow_setup.repo.get_messages(conversation_id)
            if not history:
                raise ValueError(f"Conversation {conversation_id} not found")
            uow_setup.repo.truncate_from(conversation_id, message_id)
            uow_setup.repo.append_message(conversation_id, "user", new_content)
            uow_setup.commit()

        # Reload full history (truncated + new user message)
        uow_load = self._uow_factory()
        with uow_load:
            full_history = uow_load.repo.get_messages(conversation_id)

        trim_result = trim_history(
            full_history,
            max_turns=self._max_history_turns,
            max_tokens=self._max_history_tokens,
            conversation_id=conversation_id,
        )

        conv_id, events = stream_chat(
            messages=trim_result["messages"],
            instructions=instructions,
            llm_stream=self._llm.stream,
            conversation_id=conversation_id,
        )

        uow_final = self._uow_factory()
        return conv_id, events, used_prompt_slug, uow_final

    def persist_stream_result(
        self,
        uow: UnitOfWork,
        conversation_id: str,
        assistant_message: str,
        prompt_slug: str,
        model: str,
        ttfb_ms: int,
        total_ms: int,
    ) -> None:
        """
        Persist the final assistant message and run metadata after streaming completes.

        Transaction boundary: assistant message + run are committed atomically.
        This is called by the route after consuming the stream iterator.
        """
        with uow:
            assistant_message_id = uow.repo.append_message(
                conversation_id, "assistant", assistant_message
            )
            uow.repo.record_run(
                conversation_id=conversation_id,
                assistant_message_id=assistant_message_id,
                prompt_slug=prompt_slug,
                model=model,
                ttfb_ms=ttfb_ms,
                total_ms=total_ms,
            )
            uow.commit()
