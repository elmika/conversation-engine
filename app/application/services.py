"""Application services: orchestrate use cases + persistence."""

import logging
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

from app.application.ports import LLMPort, LLMResult, PromptRepo, SlotResolver, StreamEvent, UnitOfWork
from app.application.use_cases import chat, stream_chat
from app.domain.history import trim_history
from app.domain.lesson_flow import is_lesson_flow, phase_for_turn, resolve_phase_prompt
from app.domain.session_length import parse_session_length_minutes
from app.domain.model_registry import validate_model_slug
from app.domain.prompt_template import render_prompt, resolve_file_sections
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
        default_model: str,
        slot_resolver: SlotResolver,
        max_history_turns: Optional[int] = None,
        max_history_tokens: Optional[int] = None,
        user_id: str = "default",
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._prompt_repo = prompt_repo
        self._default_prompt_slug = default_prompt_slug
        self._default_model = default_model
        self._slot_resolver = slot_resolver
        self._max_history_turns = max_history_turns
        self._max_history_tokens = max_history_tokens
        self._user_id = user_id

    def _resolve_prompt(self, slug: Optional[str]) -> tuple[str, str, Optional[str], str]:
        """Resolve prompt slug to (used_slug, system_prompt, prompt_model, prompt_name). Falls back to default."""
        record = self._prompt_repo.get_prompt_or_default(slug, self._default_prompt_slug)
        return record["slug"], record["system_prompt"], record.get("model"), record.get("name", record["slug"])

    def _make_conversation_name(self, prompt_name: str) -> str:
        """Build conversation name from the prompt name. Module enrichment is a Layer 2 hook concern."""
        return prompt_name

    def _render_instructions(
        self, instructions: str, conversation_start: Optional[datetime] = None
    ) -> str:
        # Pass 1: expand {{course}}, {{user}}, {{progress}} via SlotResolver port
        instructions = resolve_file_sections(instructions, self._slot_resolver.resolve)

        # Pass 2: resolve {{time:*}} tags
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

    def _resolve_model(
        self,
        request_model: Optional[str],
        prompt_model: Optional[str],
    ) -> str:
        """Resolve model from request override → prompt default → global default.

        Raises ValueError if an explicitly provided slug is unknown.
        """
        slug = request_model or prompt_model or self._default_model
        return validate_model_slug(slug)

    def _resolve_effective_prompt(
        self,
        uow,
        conversation_id: str,
        prompt_slug: Optional[str],
        model_slug: Optional[str],
    ) -> tuple[str, str, str]:
        """Resolve the prompt + model for a turn on an EXISTING conversation.

        Uses the prompt baked into the conversation at creation; falls back to the
        caller's prompt_slug only for legacy rows that pre-date per-conversation
        storage. Renders the instructions anchored to the conversation's start time.

        Returns: (used_prompt_slug, rendered_instructions, resolved_model)
        """
        conv_meta = uow.repo.get_conversation(conversation_id, self._user_id)
        effective_slug = (conv_meta or {}).get("prompt_slug") or prompt_slug
        # Subsequent turn on an existing conversation → the CORE phase of the
        # lesson flow. For flat prompts this is the identity, so setup/admin
        # conversations are unaffected.
        if effective_slug:
            phase = phase_for_turn(is_opening_turn=False)
            effective_slug = resolve_phase_prompt(effective_slug, phase)
        used_prompt_slug, instructions, prompt_model, _ = self._resolve_prompt(effective_slug)
        resolved_model = self._resolve_model(model_slug, prompt_model)

        created_at = uow.repo.get_conversation_created_at(conversation_id)
        instructions = self._render_instructions(instructions, created_at)
        return used_prompt_slug, instructions, resolved_model

    def _guard_not_ended(self, uow, conversation_id: str) -> None:
        """Raise ValueError if the conversation is ended."""
        conv = uow.repo.get_conversation(conversation_id, self._user_id)
        if conv and conv["ended_at"]:
            raise ValueError("conversation_ended")

    def _guard_no_active_conversation(self, uow) -> None:
        """Raise ValueError if there is already an active (non-ended) conversation.

        Global per-user: only one active conversation at a time regardless of course.
        The active conversation ID is embedded in the message so routes can return it to callers.
        """
        active = uow.repo.get_active_conversation(self._user_id)
        if active:
            raise ValueError(f"active_conversation_exists:{active}")

    def create_and_chat(
        self,
        messages: list[dict[str, str]],
        prompt_slug: Optional[str] = None,
        model_slug: Optional[str] = None,
    ) -> tuple[str, str, str, int, int]:
        """
        Create a new conversation and run the first turn (non-streaming).

        Transaction boundary: all operations commit atomically.
        Returns: (conversation_id, assistant_message, model, ttfb_ms, total_ms)
        """
        used_prompt_slug, instructions, prompt_model, prompt_name = self._resolve_prompt(prompt_slug)
        instructions = self._render_instructions(instructions)
        resolved_model = self._resolve_model(model_slug, prompt_model)

        # Create conversation with domain-generated ID
        conv_id = ConversationId.generate()
        cid_str = str(conv_id)

        with self._uow_factory() as uow:
            self._guard_no_active_conversation(uow)
            base_name = self._make_conversation_name(prompt_name)
            count = uow.repo.count_conversations_named(base_name)
            name = base_name if count == 0 else f"{base_name} ({count + 1})"
            uow.repo.create_conversation_with_id(cid_str, name=name, user_id=self._user_id, prompt_slug=used_prompt_slug)
            for msg in messages:
                uow.repo.append_message(cid_str, msg["role"], msg["content"])

            # Call LLM with resolved model
            conversation_id, assistant_message, model, ttfb_ms, total_ms = chat(
                messages=messages,
                instructions=instructions,
                llm_complete=lambda instr, msgs: self._llm.complete(instr, msgs, model=resolved_model),
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
        model_slug: Optional[str] = None,
    ) -> tuple[str, str, str, int, int]:
        """
        Append a new turn to an existing conversation (non-streaming).

        Transaction boundary: all operations commit atomically.
        Loads history, trims to limits, combines with new messages, calls LLM, persists response.

        The prompt used is the one stored on the conversation at creation time — the caller's
        prompt_slug is only a fallback for legacy rows that pre-date per-conversation storage.

        Returns: (conversation_id, assistant_message, model, ttfb_ms, total_ms)
        Raises: ValueError if conversation not found.
        """
        with self._uow_factory() as uow:
            # Load conversation history
            history = uow.repo.get_messages(conversation_id, self._user_id)
            if not history:
                raise ValueError(f"Conversation {conversation_id} not found")

            self._guard_not_ended(uow, conversation_id)

            used_prompt_slug, instructions, resolved_model = self._resolve_effective_prompt(
                uow, conversation_id, prompt_slug, model_slug
            )

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

            # Call LLM with trimmed history and resolved model
            conv_id, assistant_message, model, ttfb_ms, total_ms = chat(
                messages=combined_messages,
                instructions=instructions,
                llm_complete=lambda instr, msgs: self._llm.complete(instr, msgs, model=resolved_model),
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
        model_slug: Optional[str] = None,
    ) -> tuple[str, Iterable[StreamEvent], str, str, UnitOfWork]:
        """
        Create a new conversation and stream the first turn.

        Transaction boundary: conversation + user messages are committed immediately.
        The UoW is returned for the caller to persist the final assistant message + run.

        Returns: (conversation_id, event_iterator, used_prompt_slug, resolved_model, uow)
        """
        used_prompt_slug, instructions, prompt_model, prompt_name = self._resolve_prompt(prompt_slug)
        instructions = self._render_instructions(instructions)
        resolved_model = self._resolve_model(model_slug, prompt_model)
        conv_id = ConversationId.generate()
        cid_str = str(conv_id)

        # Create a UoW for the initial setup (conversation + user messages)
        uow_setup = self._uow_factory()
        with uow_setup:
            self._guard_no_active_conversation(uow_setup)
            base_name = self._make_conversation_name(prompt_name)
            count = uow_setup.repo.count_conversations_named(base_name)
            name = base_name if count == 0 else f"{base_name} ({count + 1})"
            uow_setup.repo.create_conversation_with_id(cid_str, name=name, user_id=self._user_id, prompt_slug=used_prompt_slug)
            for msg in messages:
                uow_setup.repo.append_message(cid_str, msg["role"], msg["content"])
            uow_setup.commit()

        # Start streaming with resolved model
        conversation_id, events = stream_chat(
            messages=messages,
            instructions=instructions,
            llm_stream=lambda instr, msgs: self._llm.stream(instr, msgs, model=resolved_model),
            conversation_id=conv_id,
        )

        # Return a new UoW for the caller to persist the final result
        uow_final = self._uow_factory()
        return conversation_id, events, used_prompt_slug, resolved_model, uow_final

    def create_and_stream_init(
        self,
        prompt_slug: Optional[str] = None,
        model_slug: Optional[str] = None,
        name: Optional[str] = None,
    ) -> tuple[str, Iterable[StreamEvent], str, str, UnitOfWork]:
        """
        Create a new conversation and stream an AI-initiated opening message.

        No user message is stored — the LLM is called with a hidden trigger that is
        never persisted. Only the assistant's opening message lands in the conversation.

        name: optional display name for the conversation; caller is responsible for
              resolving this (e.g. from a course title). Falls back to the prompt name.

        Returns: (conversation_id, event_iterator, used_prompt_slug, resolved_model, uow)
        """
        used_prompt_slug, instructions, prompt_model, prompt_name = self._resolve_prompt(prompt_slug)
        instructions = self._render_instructions(instructions)
        resolved_model = self._resolve_model(model_slug, prompt_model)
        conv_id = ConversationId.generate()
        cid_str = str(conv_id)

        # Code-owned timing: seed the session length from the learner's profile for
        # lesson flows. Flat prompts (setup/admin) have no session and store None.
        session_length = (
            parse_session_length_minutes(self._slot_resolver.resolve("user"))
            if is_lesson_flow(used_prompt_slug)
            else None
        )

        uow_setup = self._uow_factory()
        with uow_setup:
            self._guard_no_active_conversation(uow_setup)
            base_name = name or self._make_conversation_name(prompt_name)
            count = uow_setup.repo.count_conversations_named(base_name)
            resolved_name = base_name if count == 0 else f"{base_name} ({count + 1})"
            uow_setup.repo.create_conversation_with_id(
                cid_str,
                name=resolved_name,
                user_id=self._user_id,
                prompt_slug=used_prompt_slug,
                session_length_minutes=session_length,
            )
            uow_setup.commit()

        # Hidden trigger — not stored, causes the LLM to produce the opening message
        trigger = [{"role": "user", "content": "start"}]
        conversation_id, events = stream_chat(
            messages=trigger,
            instructions=instructions,
            llm_stream=lambda instr, msgs: self._llm.stream(instr, msgs, model=resolved_model),
            conversation_id=conv_id,
        )

        uow_final = self._uow_factory()
        return conversation_id, events, used_prompt_slug, resolved_model, uow_final

    def append_and_stream(
        self,
        conversation_id: str,
        messages: list[dict[str, str]],
        prompt_slug: Optional[str] = None,
        model_slug: Optional[str] = None,
    ) -> tuple[str, Iterable[StreamEvent], str, str, UnitOfWork]:
        """
        Append a new turn to an existing conversation with streaming.

        Transaction boundary: user messages are committed immediately.
        The UoW is returned for the caller to persist the final assistant message + run.

        Loads history, trims to limits, combines with new messages, starts streaming.
        Returns: (conversation_id, event_iterator, used_prompt_slug, resolved_model, uow)
        Raises: ValueError if conversation not found.
        """
        # Load history and persist user messages in one transaction
        uow_setup = self._uow_factory()
        with uow_setup:
            history = uow_setup.repo.get_messages(conversation_id, self._user_id)
            if not history:
                raise ValueError(f"Conversation {conversation_id} not found")

            self._guard_not_ended(uow_setup, conversation_id)

            used_prompt_slug, instructions, resolved_model = self._resolve_effective_prompt(
                uow_setup, conversation_id, prompt_slug, model_slug
            )

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

        # Start streaming with full history and resolved model
        conv_id, events = stream_chat(
            messages=combined_messages,
            instructions=instructions,
            llm_stream=lambda instr, msgs: self._llm.stream(instr, msgs, model=resolved_model),
            conversation_id=conversation_id,
        )

        # Return a new UoW for the caller to persist the final result
        uow_final = self._uow_factory()
        return conv_id, events, used_prompt_slug, resolved_model, uow_final

    def rewind_and_stream(
        self,
        conversation_id: str,
        message_id: int,
        new_content: str,
        prompt_slug: Optional[str] = None,
        model_slug: Optional[str] = None,
    ) -> tuple[str, Iterable[StreamEvent], str, str, UnitOfWork]:
        """
        Rewind a conversation to message_id, replace it with new_content, and stream.

        Deletes message_id and everything after it, appends new_content as a user
        message, then streams the assistant's response using the retained history.

        Returns: (conversation_id, event_iterator, used_prompt_slug, resolved_model, uow)
        Raises: ValueError if conversation not found.
        """
        uow_setup = self._uow_factory()
        with uow_setup:
            history = uow_setup.repo.get_messages(conversation_id, self._user_id)
            if not history:
                raise ValueError(f"Conversation {conversation_id} not found")

            self._guard_not_ended(uow_setup, conversation_id)

            used_prompt_slug, instructions, resolved_model = self._resolve_effective_prompt(
                uow_setup, conversation_id, prompt_slug, model_slug
            )

            uow_setup.repo.truncate_from(conversation_id, message_id, self._user_id)
            uow_setup.repo.append_message(conversation_id, "user", new_content)
            uow_setup.commit()

        # Reload full history (truncated + new user message)
        uow_load = self._uow_factory()
        with uow_load:
            full_history = uow_load.repo.get_messages(conversation_id, self._user_id)

        trim_result = trim_history(
            full_history,
            max_turns=self._max_history_turns,
            max_tokens=self._max_history_tokens,
            conversation_id=conversation_id,
        )

        conv_id, events = stream_chat(
            messages=trim_result["messages"],
            instructions=instructions,
            llm_stream=lambda instr, msgs: self._llm.stream(instr, msgs, model=resolved_model),
            conversation_id=conversation_id,
        )

        uow_final = self._uow_factory()
        return conv_id, events, used_prompt_slug, resolved_model, uow_final

    def preview_prompt(
        self,
        slug: str,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """Return the prompt's system_prompt with template variables resolved.

        If conversation_id is provided, time:conversation-start and
        time:lesson-time-spent are anchored to that conversation's created_at.
        Raises ValueError if the slug or conversation_id is not found.
        """
        record = self._prompt_repo.get_prompt(slug)
        if record is None:
            raise ValueError(f"Prompt '{slug}' not found")

        created_at = None
        if conversation_id:
            with self._uow_factory() as uow:
                created_at = uow.repo.get_conversation_created_at(conversation_id)
            if created_at is None:
                raise ValueError(f"Conversation '{conversation_id}' not found")

        rendered = self._render_instructions(record["system_prompt"], created_at)
        return {"slug": record["slug"], "name": record["name"], "rendered_prompt": rendered}

    def get_active_messages(self, conversation_id: str) -> list[dict]:
        """Return the messages of an active (non-ended) conversation owned by the user.

        Used by close-triggered actions (e.g. setup completion) that must run BEFORE
        the conversation is ended, so a failure leaves the conversation resumable.
        Raises ValueError if not found / not owned, or "conversation_ended" if ended.
        """
        with self._uow_factory() as uow:
            conv = uow.repo.get_conversation(conversation_id, self._user_id)
            if not conv:
                raise ValueError(f"Conversation {conversation_id} not found")
            if conv["ended_at"]:
                raise ValueError("conversation_ended")
            return uow.repo.get_messages(conversation_id, self._user_id)

    def end_conversation(self, conversation_id: str) -> list[dict]:
        """
        Mark a conversation as ended and return its messages.

        Raises ValueError if conversation not found or already ended.
        Returns the message list so the caller can pass it to synthesise_progress.
        """
        with self._uow_factory() as uow:
            conv = uow.repo.get_conversation(conversation_id, self._user_id)
            if not conv:
                raise ValueError(f"Conversation {conversation_id} not found")
            if conv["ended_at"]:
                raise ValueError("conversation_ended")
            messages = uow.repo.get_messages(conversation_id, self._user_id)
            uow.repo.end_conversation(conversation_id, self._user_id)
            uow.commit()
        return messages

    def persist_stream_result(
        self,
        uow: UnitOfWork,
        conversation_id: str,
        assistant_message: str,
        prompt_slug: str,
        model: str,
        ttfb_ms: int,
        total_ms: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
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
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            uow.commit()
