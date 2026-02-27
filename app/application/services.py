"""Application services: orchestrate use cases + persistence."""

from collections.abc import Callable, Iterable
from typing import Optional

from app.application.ports import LLMPort, LLMResult, StreamEvent, UnitOfWork
from app.application.use_cases import chat, stream_chat
from app.domain.value_objects import ConversationId


class ConversationService:
    """
    Service layer for conversation workflows.
    
    Orchestrates: load history → call LLM → persist → return result.
    Each service method defines a transaction boundary using UnitOfWork.
    Routes become thin glue that validates input and formats HTTP/SSE responses.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        llm: LLMPort,
        default_prompt_slug: str,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._default_prompt_slug = default_prompt_slug

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
        used_prompt_slug = prompt_slug or self._default_prompt_slug
        
        # Create conversation with domain-generated ID
        conv_id = ConversationId.generate()
        cid_str = str(conv_id)
        
        with self._uow_factory() as uow:
            # Persist conversation and user messages
            uow.repo.create_conversation_with_id(cid_str)
            for msg in messages:
                uow.repo.append_message(cid_str, msg["role"], msg["content"])
            
            # Call LLM (use case now uses domain ConversationId internally)
            conversation_id, assistant_message, model, ttfb_ms, total_ms = chat(
                messages=messages,
                prompt_slug=prompt_slug,
                default_slug=self._default_prompt_slug,
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
        Loads history, combines with new messages, calls LLM, persists response.
        Returns: (conversation_id, assistant_message, model, ttfb_ms, total_ms)
        Raises: ValueError if conversation not found.
        """
        used_prompt_slug = prompt_slug or self._default_prompt_slug
        
        with self._uow_factory() as uow:
            # Load conversation history
            history = uow.repo.get_messages(conversation_id)
            if not history:
                raise ValueError(f"Conversation {conversation_id} not found")
            
            # Persist user messages for this turn
            for msg in messages:
                uow.repo.append_message(conversation_id, msg["role"], msg["content"])
            
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
        used_prompt_slug = prompt_slug or self._default_prompt_slug
        conv_id = ConversationId.generate()
        cid_str = str(conv_id)
        
        # Create a UoW for the initial setup (conversation + user messages)
        uow_setup = self._uow_factory()
        with uow_setup:
            uow_setup.repo.create_conversation_with_id(cid_str)
            for msg in messages:
                uow_setup.repo.append_message(cid_str, msg["role"], msg["content"])
            uow_setup.commit()
        
        # Start streaming
        conversation_id, events = stream_chat(
            messages=messages,
            prompt_slug=prompt_slug,
            default_slug=self._default_prompt_slug,
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
        
        Loads history, combines with new messages, starts streaming.
        Returns: (conversation_id, event_iterator, used_prompt_slug, uow)
        Raises: ValueError if conversation not found.
        """
        used_prompt_slug = prompt_slug or self._default_prompt_slug
        
        # Load history and persist user messages in one transaction
        uow_setup = self._uow_factory()
        with uow_setup:
            history = uow_setup.repo.get_messages(conversation_id)
            if not history:
                raise ValueError(f"Conversation {conversation_id} not found")
            
            for msg in messages:
                uow_setup.repo.append_message(conversation_id, msg["role"], msg["content"])
            uow_setup.commit()
        
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
        
        # Return a new UoW for the caller to persist the final result
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
