"""API routes."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import ConversationRequest, ConversationResponse, TimingsSchema
from app.application.ports import ConversationRepo, LLMPort
from app.application.services import ConversationService
from app.infra.persistence.db import get_session
from app.infra.persistence.repo_sqlalchemy import SQLAlchemyConversationRepo
from app.settings import Settings

router = APIRouter()


def get_settings(request: Request) -> Settings:
    """Provide settings from app.state (injected in main lifespan)."""
    return request.app.state.settings


def get_llm(request: Request) -> LLMPort:
    """Provide LLM adapter from app.state (injected in main lifespan)."""
    return request.app.state.llm


def get_repo(db=Depends(get_session)) -> ConversationRepo:
    """Provide conversation repository (SQLAlchemy impl, session from app engine)."""
    return SQLAlchemyConversationRepo(db)


def get_conversation_service(
    repo: ConversationRepo = Depends(get_repo),
    llm: LLMPort = Depends(get_llm),
    settings: Settings = Depends(get_settings),
) -> ConversationService:
    """Provide conversation service with injected dependencies."""
    return ConversationService(
        repo=repo,
        llm=llm,
        default_prompt_slug=settings.default_prompt_slug,
    )


def _check_input_length(messages: list[dict[str, str]], max_chars: int) -> None:
    """Raise 400 if total message content length exceeds max_chars."""
    total = sum(len(m.get("content") or "") for m in messages)
    if total > max_chars:
        raise HTTPException(
            status_code=400,
            detail=f"Total message content length ({total}) exceeds max_input_chars ({max_chars})",
        )


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
    service: ConversationService = Depends(get_conversation_service),
) -> StreamingResponse:
    """
    Create a new conversation and stream the first turn as SSE.

    Emits SSE events:
      - meta: conversation_id, model, prompt_slug
      - chunk: incremental text delta
      - done: final assistant message + timings
    """
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    _check_input_length(messages, settings.max_input_chars)

    async def event_generator() -> AsyncIterator[str]:
        conv_id, events, used_prompt_slug = await asyncio.to_thread(
            service.create_and_stream,
            messages,
            body.prompt_slug,
        )

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

                await asyncio.to_thread(
                    service.persist_stream_result,
                    conv_id,
                    full_text,
                    used_prompt_slug,
                    model,
                    ttfb_ms,
                    total_ms,
                )
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
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    """Create a new conversation and handle the first turn (non-streaming)."""
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    _check_input_length(messages, settings.max_input_chars)

    conversation_id, assistant_message, model, ttfb_ms, total_ms = await asyncio.to_thread(
        service.create_and_chat,
        messages,
        body.prompt_slug,
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
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    """Append a new turn to an existing conversation (non-streaming)."""
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    _check_input_length(messages, settings.max_input_chars)

    def _run() -> tuple[str, str, str, int, int]:
        try:
            return service.append_and_chat(conversation_id, messages, body.prompt_slug)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

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
    service: ConversationService = Depends(get_conversation_service),
) -> StreamingResponse:
    """
    Append a new turn to an existing conversation with streaming SSE output.

    Emits SSE events:
      - meta: conversation_id, model, prompt_slug
      - chunk: incremental text delta
      - done: final assistant message + timings
    """
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    _check_input_length(messages, settings.max_input_chars)

    async def event_generator() -> AsyncIterator[str]:
        def _stream_setup() -> tuple[str, Any, str]:
            try:
                return service.append_and_stream(conversation_id, messages, body.prompt_slug)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        conv_id, events, used_prompt_slug = await asyncio.to_thread(_stream_setup)

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

                await asyncio.to_thread(
                    service.persist_stream_result,
                    conv_id,
                    full_text,
                    used_prompt_slug,
                    model,
                    ttfb_ms,
                    total_ms,
                )
                done_payload = {
                    "conversation_id": conv_id,
                    "assistant_message": full_text,
                    "model": model,
                    "timings": {"ttfb_ms": ttfb_ms, "total_ms": total_ms},
                }
                yield _sse_event("done", done_payload)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
