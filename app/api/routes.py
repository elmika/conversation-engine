"""API routes."""

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.schemas import ChatRequest, ChatResponse, TimingsSchema
from app.application.use_cases import chat, stream_chat
from app.infra.llm_openai import OpenAILLMAdapter
from app.settings import Settings

router = APIRouter()


def get_settings() -> Settings:
    """Load settings (inject in main with overrides if needed)."""
    return Settings()


def get_llm(settings: Settings = Depends(get_settings)) -> OpenAILLMAdapter:
    """Provide LLM adapter."""
    return OpenAILLMAdapter(settings)


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    body: ChatRequest,
    settings: Settings = Depends(get_settings),
    llm: OpenAILLMAdapter = Depends(get_llm),
) -> ChatResponse:
    """Non-streaming chat; returns full response with timings."""
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    def _run() -> tuple[str, str, str, int, int]:
        return chat(
            messages=messages,
            prompt_slug=body.prompt_slug,
            default_slug=settings.default_prompt_slug,
            llm_complete=llm.complete,
            conversation_id=body.conversation_id,
        )

    conversation_id, assistant_message, model, ttfb_ms, total_ms = await asyncio.to_thread(_run)
    return ChatResponse(
        conversation_id=conversation_id,
        assistant_message=assistant_message,
        model=model,
        timings=TimingsSchema(ttfb_ms=ttfb_ms, total_ms=total_ms),
    )


def _sse_event(event: str, data: dict[str, Any]) -> str:
    """Format a server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/chat/stream")
async def post_chat_stream(
    body: ChatRequest,
    settings: Settings = Depends(get_settings),
    llm: OpenAILLMAdapter = Depends(get_llm),
) -> StreamingResponse:
    """
    Streaming chat endpoint.

    Emits SSE events:
      - meta: conversation_id, model, prompt_slug
      - chunk: incremental text delta
      - done: final assistant message + timings
    """
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    # Run domain logic and streaming adapter in a thread so we don't block the event loop.
    def _stream_setup() -> tuple[str, Any]:
        cid, events = stream_chat(
            messages=messages,
            prompt_slug=body.prompt_slug,
            default_slug=settings.default_prompt_slug,
            llm_stream=llm.stream,
            conversation_id=body.conversation_id,
        )
        return cid, events

    async def event_generator() -> AsyncIterator[str]:
        conversation_id, events = await asyncio.to_thread(_stream_setup)

        # Meta event first.
        meta = {
            "conversation_id": conversation_id,
            "model": settings.openai_model,
            "prompt_slug": body.prompt_slug or settings.default_prompt_slug,
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
                done_payload = {
                    "conversation_id": conversation_id,
                    "assistant_message": full_text,
                    "model": model,
                    "timings": {"ttfb_ms": ttfb_ms, "total_ms": total_ms},
                }
                yield _sse_event("done", done_payload)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
