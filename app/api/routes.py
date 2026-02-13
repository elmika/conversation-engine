"""API routes."""

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, Path
from fastapi.responses import StreamingResponse

from app.api.schemas import ConversationRequest, ConversationResponse, TimingsSchema
from app.application.use_cases import chat, stream_chat
from app.infra.llm_openai import OpenAILLMAdapter
from app.infra.persistence.db import get_session
from app.infra.persistence.repo_sqlalchemy import SQLAlchemyConversationRepo
from app.settings import Settings

router = APIRouter()


def get_settings() -> Settings:
    """Load settings (inject in main with overrides if needed)."""
    return Settings()


def get_llm(settings: Settings = Depends(get_settings)) -> OpenAILLMAdapter:
    """Provide LLM adapter."""
    return OpenAILLMAdapter(settings)


def get_repo(db=Depends(get_session)) -> SQLAlchemyConversationRepo:
    """Provide conversation repository backed by SQLAlchemy."""
    return SQLAlchemyConversationRepo(db)


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


@router.post(
    "/conversations/stream",
    name="create_conversation_stream",
)
async def create_conversation_stream(
    body: ConversationRequest,
    settings: Settings = Depends(get_settings),
    llm: OpenAILLMAdapter = Depends(get_llm),
    repo: SQLAlchemyConversationRepo = Depends(get_repo),
) -> StreamingResponse:
    """
    Create a new conversation and stream the first turn as SSE.

    Emits SSE events:
      - meta: conversation_id, model, prompt_slug
      - chunk: incremental text delta
      - done: final assistant message + timings
    """
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    # Run domain logic and streaming adapter in a thread so we don't block the event loop.
    def _stream_setup() -> tuple[str, Any, str]:
        used_prompt_slug = body.prompt_slug or settings.default_prompt_slug
        cid = repo.create_conversation()

        # Persist user messages for this first turn.
        for msg in messages:
            repo.append_message(cid, msg["role"], msg["content"])

        cid2, events = stream_chat(
            messages=messages,
            prompt_slug=body.prompt_slug,
            default_slug=settings.default_prompt_slug,
            llm_stream=llm.stream,
            conversation_id=cid,
        )
        return cid2, events, used_prompt_slug

    async def event_generator() -> AsyncIterator[str]:
        conv_id, events, used_prompt_slug = await asyncio.to_thread(_stream_setup)

        # Meta event first.
        meta = {
            "conversation_id": conv_id,
            "model": settings.openai_model,
            "prompt_slug": used_prompt_slug,
        }
        yield _sse_event("meta", meta)

        assistant_text_parts: list[str] = []
        ttfb_ms = 0
        total_ms = 0
        model = settings.openai_model

        for ev in events:
            if ev.get("type") == "delta":
                delta = ev.get("delta", "")
                if not delta:
                    continue
                assistant_text_parts.append(delta)
                if ev.get("ttfb_ms"):
                    ttfb_ms = ev["ttfb_ms"]
                if ev.get("model"):
                    model = ev["model"]
                if ev.get("total_ms"):
                    total_ms = ev["total_ms"]
                yield _sse_event("chunk", {"delta": delta})
            elif ev.get("type") == "final":
                full_text = ev.get("text", "") or "".join(assistant_text_parts)
                if ev.get("model"):
                    model = ev["model"]
                if ev.get("ttfb_ms"):
                    ttfb_ms = ev["ttfb_ms"]
                if ev.get("total_ms"):
                    total_ms = ev["total_ms"]

                # Persist assistant message and run metadata in a worker thread.
                def _inner() -> None:
                    assistant_message_id = repo.append_message(conv_id, "assistant", full_text)
                    repo.record_run(
                        conversation_id=conv_id,
                        assistant_message_id=assistant_message_id,
                        prompt_slug=used_prompt_slug,
                        model=model,
                        ttfb_ms=ttfb_ms,
                        total_ms=total_ms,
                    )

                await asyncio.to_thread(_inner)
                done_payload = {
                    "conversation_id": conv_id,
                    "assistant_message": full_text,
                    "model": model,
                    "timings": {"ttfb_ms": ttfb_ms, "total_ms": total_ms},
                }
                yield _sse_event("done", done_payload)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/conversations", name="create_conversation", response_model=ConversationResponse)
async def create_conversation(
    body: ConversationRequest,
    settings: Settings = Depends(get_settings),
    llm: OpenAILLMAdapter = Depends(get_llm),
    repo: SQLAlchemyConversationRepo = Depends(get_repo),
    ) -> ConversationResponse:
    """Create a new conversation and handle the first turn (non-streaming)."""
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    prompt_slug = body.prompt_slug or settings.default_prompt_slug

    def _run() -> tuple[str, str, str, int, int]:
        # Create a new conversation.
        cid = repo.create_conversation()

        # Persist user messages for this turn.
        for msg in messages:
            repo.append_message(cid, msg["role"], msg["content"])

        conversation_id, assistant_message, model, ttfb_ms, total_ms = chat(
            messages=messages,
            prompt_slug=body.prompt_slug,
            default_slug=settings.default_prompt_slug,
            llm_complete=llm.complete,
            conversation_id=cid,
        )

        # Persist assistant message and run metadata.
        assistant_message_id = repo.append_message(
            conversation_id, "assistant", assistant_message
        )
        repo.record_run(
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            prompt_slug=prompt_slug,
            model=model,
            ttfb_ms=ttfb_ms,
            total_ms=total_ms,
        )
        return conversation_id, assistant_message, model, ttfb_ms, total_ms

    conversation_id, assistant_message, model, ttfb_ms, total_ms = await asyncio.to_thread(
        _run
    )
    return ConversationResponse(
        conversation_id=conversation_id,
        assistant_message=assistant_message,
        model=model,
        timings=TimingsSchema(ttfb_ms=ttfb_ms, total_ms=total_ms),
    )


def _sse_event(event: str, data: dict[str, Any]) -> str:
    """Format a server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post(
    "/conversations/{conversation_id}",
    name="append_conversation_turn",
    response_model=ConversationResponse,
)
async def append_conversation_turn(
    conversation_id: str,
    body: ConversationRequest,
    settings: Settings = Depends(get_settings),
    llm: OpenAILLMAdapter = Depends(get_llm),
    repo: SQLAlchemyConversationRepo = Depends(get_repo),
) -> ConversationResponse:
    """Append a new turn to an existing conversation (non-streaming)."""
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    prompt_slug = body.prompt_slug or settings.default_prompt_slug

    def _run() -> tuple[str, str, str, int, int]:
        cid = conversation_id

        # Persist user messages for this turn.
        for msg in messages:
            repo.append_message(cid, msg["role"], msg["content"])

        conv_id, assistant_message, model, ttfb_ms, total_ms = chat(
            messages=messages,
            prompt_slug=body.prompt_slug,
            default_slug=settings.default_prompt_slug,
            llm_complete=llm.complete,
            conversation_id=cid,
        )

        # Persist assistant message and run metadata.
        assistant_message_id = repo.append_message(conv_id, "assistant", assistant_message)
        repo.record_run(
            conversation_id=conv_id,
            assistant_message_id=assistant_message_id,
            prompt_slug=prompt_slug,
            model=model,
            ttfb_ms=ttfb_ms,
            total_ms=total_ms,
        )
        return conv_id, assistant_message, model, ttfb_ms, total_ms

    conv_id, assistant_message, model, ttfb_ms, total_ms = await asyncio.to_thread(_run)
    return ConversationResponse(
        conversation_id=conv_id,
        assistant_message=assistant_message,
        model=model,
        timings=TimingsSchema(ttfb_ms=ttfb_ms, total_ms=total_ms),
    )


@router.post(
    "/conversations/{conversation_id}/stream",
    name="append_conversation_turn_stream",
)
async def append_conversation_turn_stream(
    conversation_id: str,
    body: ConversationRequest,
    settings: Settings = Depends(get_settings),
    llm: OpenAILLMAdapter = Depends(get_llm),
    repo: SQLAlchemyConversationRepo = Depends(get_repo),
) -> StreamingResponse:
    """
    Append a new turn to an existing conversation with streaming SSE output.

    Emits SSE events:
      - meta: conversation_id, model, prompt_slug
      - chunk: incremental text delta
      - done: final assistant message + timings
    """
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    # Run domain logic and streaming adapter in a thread so we don't block the event loop.
    def _stream_setup() -> tuple[str, Any, str]:
        used_prompt_slug = body.prompt_slug or settings.default_prompt_slug
        cid = conversation_id

        # Persist user messages for this turn.
        for msg in messages:
            repo.append_message(cid, msg["role"], msg["content"])

        cid2, events = stream_chat(
            messages=messages,
            prompt_slug=body.prompt_slug,
            default_slug=settings.default_prompt_slug,
            llm_stream=llm.stream,
            conversation_id=cid,
        )
        return cid2, events, used_prompt_slug

    async def event_generator() -> AsyncIterator[str]:
        conv_id, events, used_prompt_slug = await asyncio.to_thread(_stream_setup)

        # Meta event first.
        meta = {
            "conversation_id": conv_id,
            "model": settings.openai_model,
            "prompt_slug": used_prompt_slug,
        }
        yield _sse_event("meta", meta)

        assistant_text_parts: list[str] = []
        ttfb_ms = 0
        total_ms = 0
        model = settings.openai_model

        for ev in events:
            if ev.get("type") == "delta":
                delta = ev.get("delta", "")
                if not delta:
                    continue
                assistant_text_parts.append(delta)
                if ev.get("ttfb_ms"):
                    ttfb_ms = ev["ttfb_ms"]
                if ev.get("model"):
                    model = ev["model"]
                if ev.get("total_ms"):
                    total_ms = ev["total_ms"]
                yield _sse_event("chunk", {"delta": delta})
            elif ev.get("type") == "final":
                full_text = ev.get("text", "") or "".join(assistant_text_parts)
                if ev.get("model"):
                    model = ev["model"]
                if ev.get("ttfb_ms"):
                    ttfb_ms = ev["ttfb_ms"]
                if ev.get("total_ms"):
                    total_ms = ev["total_ms"]

                # Persist assistant message and run metadata in a worker thread.
                def _inner() -> None:
                    assistant_message_id = repo.append_message(conv_id, "assistant", full_text)
                    repo.record_run(
                        conversation_id=conv_id,
                        assistant_message_id=assistant_message_id,
                        prompt_slug=used_prompt_slug,
                        model=model,
                        ttfb_ms=ttfb_ms,
                        total_ms=total_ms,
                    )

                await asyncio.to_thread(_inner)
                done_payload = {
                    "conversation_id": conv_id,
                    "assistant_message": full_text,
                    "model": model,
                    "timings": {"ttfb_ms": ttfb_ms, "total_ms": total_ms},
                }
                yield _sse_event("done", done_payload)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
