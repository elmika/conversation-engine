"""API routes."""

import asyncio

from fastapi import APIRouter, Depends

from app.api.schemas import ChatRequest, ChatResponse, TimingsSchema
from app.application.use_cases import chat
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
