"""Application services: orchestrate use cases + persistence."""

from collections.abc import Iterable
from typing import Optional

from app.application.ports import ConversationRepo, LLMPort, LLMResult, StreamEvent
from app.application.use_cases import chat, stream_chat
from app.domain.value_objects import ConversationId


class ConversationService:
    """
    Service layer for conversation workflows.
    
    Orchestrates: load history → call LLM → persist → return result.
    Routes become thin glue that validates input and formats HTTP/SSE responses.
    """

    def __init__(
        self,
        repo: ConversationRepo,
        llm: LLMPort,
        default_prompt_slug: str,
    ) -> None:
        self._repo = repo
        self._llm = llm
        self._default_prompt_slug = default_prompt_slug

    def create_and_chat(
        self,
        messages: list[dict[str, str]],
        prompt_slug: Optional[str] = None,
    ) -> tuple[str, str, str, int, int]:
        """
        Create a new conversation and run the first turn (non-streaming).
        
        Returns: (conversation_id, assistant_message, model, ttfb_ms, total_ms)
        """
        used_prompt_slug = prompt_slug or self._default_prompt_slug
        
        # Create conversation with domain-generated ID
        conv_id = ConversationId.generate()
        cid_str = str(conv_id)
        self._repo.create_conversation_with_id(cid_str)
        
        # Persist user messages for this turn
        for msg in messages:
            self._repo.append_message(cid_str, msg["role"], msg["content"])
        
        # Call LLM (use case now uses domain ConversationId internally)
        conversation_id, assistant_message, model, ttfb_ms, total_ms = chat(
            messages=messages,
            prompt_slug=prompt_slug,
            default_slug=self._default_prompt_slug,
            llm_complete=self._llm.complete,
            conversation_id=conv_id,
        )
        
        # Persist assistant message and run metadata
        assistant_message_id = self._repo.append_message(
            conversation_id, "assistant", assistant_message
        )
        self._repo.record_run(
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            prompt_slug=used_prompt_slug,
            model=model,
            ttfb_ms=ttfb_ms,
            total_ms=total_ms,
        )
        
        return conversation_id, assistant_message, model, ttfb_ms, total_ms

    def append_and_chat(
        self,
        conversation_id: str,
        messages: list[dict[str, str]],
        prompt_slug: Optional[str] = None,
    ) -> tuple[str, str, str, int, int]:
        """
        Append a new turn to an existing conversation (non-streaming).
        
        Loads history, combines with new messages, calls LLM, persists response.
        Returns: (conversation_id, assistant_message, model, ttfb_ms, total_ms)
        Raises: ValueError if conversation not found.
        """
        used_prompt_slug = prompt_slug or self._default_prompt_slug
        
        # Load conversation history
        history = self._repo.get_messages(conversation_id)
        if not history:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        # Persist user messages for this turn
        for msg in messages:
            self._repo.append_message(conversation_id, msg["role"], msg["content"])
        
        # Combine history with new messages
        combined_messages = history + messages
        
        # Call LLM with full history
        conv_id, assistant_message, model, ttfb_ms, total_ms = chat(
            messages=combined_messages,
            prompt_slug=prompt_slug,
            default_slug=self._default_prompt_slug,
            llm_complete=self._llm.complete,
            conversation_id=conversation_id,
        )
        
        # Persist assistant message and run metadata
        assistant_message_id = self._repo.append_message(
            conv_id, "assistant", assistant_message
        )
        self._repo.record_run(
            conversation_id=conv_id,
            assistant_message_id=assistant_message_id,
            prompt_slug=used_prompt_slug,
            model=model,
            ttfb_ms=ttfb_ms,
            total_ms=total_ms,
        )
        
        return conv_id, assistant_message, model, ttfb_ms, total_ms

    def create_and_stream(
        self,
        messages: list[dict[str, str]],
        prompt_slug: Optional[str] = None,
    ) -> tuple[str, Iterable[StreamEvent], str]:
        """
        Create a new conversation and stream the first turn.
        
        Returns: (conversation_id, event_iterator, used_prompt_slug)
        The caller is responsible for iterating events and persisting the final message.
        """
        used_prompt_slug = prompt_slug or self._default_prompt_slug
        
        # Create conversation
        cid = self._repo.create_conversation()
        
        # Persist user messages for this turn
        for msg in messages:
            self._repo.append_message(cid, msg["role"], msg["content"])
        
        # Start streaming
        conversation_id, events = stream_chat(
            messages=messages,
            prompt_slug=prompt_slug,
            default_slug=self._default_prompt_slug,
            llm_stream=self._llm.stream,
            conversation_id=cid,
        )
        
        return conversation_id, events, used_prompt_slug

    def append_and_stream(
        self,
        conversation_id: str,
        messages: list[dict[str, str]],
        prompt_slug: Optional[str] = None,
    ) -> tuple[str, Iterable[StreamEvent], str]:
        """
        Append a new turn to an existing conversation with streaming.
        
        Loads history, combines with new messages, starts streaming.
        Returns: (conversation_id, event_iterator, used_prompt_slug)
        The caller is responsible for iterating events and persisting the final message.
        Raises: ValueError if conversation not found.
        """
        used_prompt_slug = prompt_slug or self._default_prompt_slug
        
        # Load conversation history
        history = self._repo.get_messages(conversation_id)
        if not history:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        # Persist user messages for this turn
        for msg in messages:
            self._repo.append_message(conversation_id, msg["role"], msg["content"])
        
        # Combine history with new messages
        combined_messages = history + messages
        
        # Start streaming with full history
        conv_id, events = stream_chat(
            messages=combined_messages,
            prompt_slug=prompt_slug,
            default_slug=self._default_prompt_slug,
            llm_stream=self._llm.stream,
            conversation_id=conversation_id,
        )
        
        return conv_id, events, used_prompt_slug

    def persist_stream_result(
        self,
        conversation_id: str,
        assistant_message: str,
        prompt_slug: str,
        model: str,
        ttfb_ms: int,
        total_ms: int,
    ) -> None:
        """
        Persist the final assistant message and run metadata after streaming completes.
        
        This is called by the route after consuming the stream iterator.
        """
        assistant_message_id = self._repo.append_message(
            conversation_id, "assistant", assistant_message
        )
        self._repo.record_run(
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            prompt_slug=prompt_slug,
            model=model,
            ttfb_ms=ttfb_ms,
            total_ms=total_ms,
        )
