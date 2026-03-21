"""API routes."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    ConversationListResponse,
    ConversationRenameRequest,
    ConversationRequest,
    ConversationResponse,
    ConversationRewindRequest,
    ConversationSummary,
    MessageSchema,
    MessagesResponse,
    ModelSchema,
    ModelsResponse,
    PromptCreateRequest,
    PromptSchema,
    PromptUpdateRequest,
    PromptsResponse,
    TimingsSchema,
)
from app.application.ports import LLMPort, PromptRepo, UnitOfWork
from app.application.services import ConversationService
from app.domain.model_registry import list_models
from app.infra.persistence.db import get_session
from app.infra.persistence.repo_prompt import SQLAlchemyPromptRepo
from app.infra.persistence.unit_of_work import SQLAlchemyUnitOfWork
from app.settings import Settings

router = APIRouter()


def get_settings(request: Request) -> Settings:
    """Provide settings from app.state (injected in main lifespan)."""
    return request.app.state.settings


def get_llm(request: Request) -> LLMPort:
    """Provide LLM adapter from app.state (injected in main lifespan)."""
    return request.app.state.llm


def get_uow_factory(db=Depends(get_session)):
    """Provide a UnitOfWork factory that creates UoW instances with the current session."""
    def _factory() -> UnitOfWork:
        return SQLAlchemyUnitOfWork(db)
    return _factory


def get_prompt_repo(db=Depends(get_session)) -> PromptRepo:
    """Provide a PromptRepo for the current request session."""
    return SQLAlchemyPromptRepo(db)


def get_conversation_service(
    uow_factory=Depends(get_uow_factory),
    llm: LLMPort = Depends(get_llm),
    prompt_repo: PromptRepo = Depends(get_prompt_repo),
    settings: Settings = Depends(get_settings),
) -> ConversationService:
    """Provide conversation service with injected dependencies."""
    return ConversationService(
        uow_factory=uow_factory,
        llm=llm,
        prompt_repo=prompt_repo,
        default_prompt_slug=settings.default_prompt_slug,
        default_model=settings.openai_model,
        max_history_turns=settings.max_history_turns,
        max_history_tokens=settings.max_history_tokens,
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


@router.get("/models", response_model=ModelsResponse)
async def list_models_endpoint() -> ModelsResponse:
    """List all supported models from the model registry."""
    return ModelsResponse(models=[ModelSchema(**m) for m in list_models()])


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
        try:
            conv_id, events, used_prompt_slug, resolved_model, uow = await asyncio.to_thread(
                service.create_and_stream,
                messages,
                body.prompt_slug,
                body.model_slug,
            )

            meta = {
                "conversation_id": conv_id,
                "model": resolved_model,
                "prompt_slug": used_prompt_slug,
            }
            yield _sse_event("meta", meta)

            assistant_text_parts: list[str] = []
            ttfb_ms = 0
            total_ms = 0
            model = resolved_model

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
                        uow,
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
        except HTTPException as exc:
            # Map HTTP exceptions to SSE error events
            error_payload = {
                "error": {
                    "type": "http_error",
                    "status_code": exc.status_code,
                    "message": exc.detail,
                }
            }
            yield _sse_event("done", error_payload)
        except Exception as exc:
            # Catch any other errors and emit terminal done event
            error_payload = {
                "error": {
                    "type": "internal_error",
                    "message": "An unexpected error occurred during streaming",
                }
            }
            yield _sse_event("done", error_payload)
            # Re-raise so middleware can log it
            raise

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

    try:
        conversation_id, assistant_message, model, ttfb_ms, total_ms = await asyncio.to_thread(
            service.create_and_chat,
            messages,
            body.prompt_slug,
            body.model_slug,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
            return service.append_and_chat(
                conversation_id, messages, body.prompt_slug, body.model_slug
            )
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
        try:
            def _stream_setup() -> tuple[str, Any, str, str, UnitOfWork]:
                try:
                    return service.append_and_stream(
                        conversation_id, messages, body.prompt_slug, body.model_slug
                    )
                except ValueError as e:
                    raise HTTPException(status_code=404, detail=str(e))

            conv_id, events, used_prompt_slug, resolved_model, uow = await asyncio.to_thread(
                _stream_setup
            )

            meta = {
                "conversation_id": conv_id,
                "model": resolved_model,
                "prompt_slug": used_prompt_slug,
            }
            yield _sse_event("meta", meta)

            assistant_text_parts: list[str] = []
            ttfb_ms = 0
            total_ms = 0
            model = resolved_model

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
                        uow,
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
        except HTTPException as exc:
            # Map HTTP exceptions to SSE error events
            error_payload = {
                "error": {
                    "type": "http_error",
                    "status_code": exc.status_code,
                    "message": exc.detail,
                }
            }
            yield _sse_event("done", error_payload)
        except Exception as exc:
            # Catch any other errors and emit terminal done event
            error_payload = {
                "error": {
                    "type": "internal_error",
                    "message": "An unexpected error occurred during streaming",
                }
            }
            yield _sse_event("done", error_payload)
            # Re-raise so middleware can log it
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post(
    "/conversations/{conversation_id}/rewind/stream",
    name="rewind_conversation_stream",
)
async def rewind_conversation_stream(
    conversation_id: str,
    body: ConversationRewindRequest,
    settings: Settings = Depends(get_settings),
    service: ConversationService = Depends(get_conversation_service),
) -> StreamingResponse:
    """
    Rewind a conversation to a past user message, replace it with new content, and stream.

    Deletes message_id and all subsequent messages, appends new content as a user
    message, then streams the assistant response as SSE.

    Emits SSE events:
      - meta: conversation_id, model, prompt_slug
      - chunk: incremental text delta
      - done: final assistant message + timings
    """
    async def event_generator() -> AsyncIterator[str]:
        try:
            def _rewind_setup() -> tuple[str, Any, str, str, UnitOfWork]:
                try:
                    return service.rewind_and_stream(
                        conversation_id,
                        body.message_id,
                        body.content,
                        body.prompt_slug,
                        body.model_slug,
                    )
                except ValueError as e:
                    raise HTTPException(status_code=404, detail=str(e))

            conv_id, events, used_prompt_slug, resolved_model, uow = await asyncio.to_thread(
                _rewind_setup
            )

            meta = {
                "conversation_id": conv_id,
                "model": resolved_model,
                "prompt_slug": used_prompt_slug,
            }
            yield _sse_event("meta", meta)

            assistant_text_parts: list[str] = []
            ttfb_ms = 0
            total_ms = 0
            model = resolved_model

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
                        uow,
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
        except HTTPException as exc:
            error_payload = {
                "error": {
                    "type": "http_error",
                    "status_code": exc.status_code,
                    "message": exc.detail,
                }
            }
            yield _sse_event("done", error_payload)
        except Exception:
            error_payload = {
                "error": {
                    "type": "internal_error",
                    "message": "An unexpected error occurred during streaming",
                }
            }
            yield _sse_event("done", error_payload)
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = 1,
    page_size: int = 20,
    uow_factory=Depends(get_uow_factory),
) -> ConversationListResponse:
    """List conversations with pagination, ordered by created_at DESC."""
    def _run() -> tuple[list[dict], int]:
        with uow_factory() as uow:
            return uow.repo.list_conversations(page, page_size)

    rows, total = await asyncio.to_thread(_run)
    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                id=r["id"],
                name=r.get("name"),
                created_at=r["created_at"],
                last_activity=r.get("last_activity"),
                first_message=r.get("first_message"),
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    uow_factory=Depends(get_uow_factory),
) -> None:
    """Delete a conversation and all its messages."""
    def _run() -> None:
        with uow_factory() as uow:
            uow.repo.delete_conversation(conversation_id)
            uow.commit()

    await asyncio.to_thread(_run)


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
async def rename_conversation(
    conversation_id: str,
    body: ConversationRenameRequest,
    uow_factory=Depends(get_uow_factory),
) -> ConversationSummary:
    """Rename a conversation."""
    def _run() -> None:
        with uow_factory() as uow:
            uow.repo.rename_conversation(conversation_id, body.name)
            uow.commit()

    await asyncio.to_thread(_run)
    return ConversationSummary(id=conversation_id, name=body.name, created_at="")


@router.get("/conversations/{conversation_id}/messages", response_model=MessagesResponse)
async def get_conversation_messages(
    conversation_id: str,
    uow_factory=Depends(get_uow_factory),
) -> MessagesResponse:
    """Get all messages for a conversation, ordered by id ASC."""
    def _run() -> list[dict]:
        with uow_factory() as uow:
            return uow.repo.get_messages_with_metadata(conversation_id)

    msgs = await asyncio.to_thread(_run)
    return MessagesResponse(
        conversation_id=conversation_id,
        messages=[
            MessageSchema(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                created_at=m["created_at"],
            )
            for m in msgs
        ],
    )


@router.get("/prompts", response_model=PromptsResponse)
async def list_prompts(
    all: bool = False,
    prompt_repo: PromptRepo = Depends(get_prompt_repo),
) -> PromptsResponse:
    """List prompts. By default returns only active prompts; pass ?all=true to include disabled."""
    rows = await asyncio.to_thread(prompt_repo.list_prompts, all)
    prompts = [
        PromptSchema(
            slug=r["slug"],
            name=r["name"],
            system_prompt=r["system_prompt"],
            model=r.get("model"),
            is_active=r.get("is_active", True),
        )
        for r in rows
    ]
    return PromptsResponse(prompts=prompts)


@router.post("/prompts", response_model=PromptSchema, status_code=201)
async def create_prompt(
    body: PromptCreateRequest,
    prompt_repo: PromptRepo = Depends(get_prompt_repo),
    db=Depends(get_session),
) -> PromptSchema:
    """Create a new prompt persona."""
    try:
        await asyncio.to_thread(
            prompt_repo.create, body.slug, body.name, body.system_prompt, body.model
        )
        await asyncio.to_thread(db.commit)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return PromptSchema(
        slug=body.slug,
        name=body.name,
        system_prompt=body.system_prompt,
        model=body.model,
        is_active=True,
    )


@router.put("/prompts/{slug}", response_model=PromptSchema)
async def update_prompt(
    slug: str,
    body: PromptUpdateRequest,
    prompt_repo: PromptRepo = Depends(get_prompt_repo),
    db=Depends(get_session),
) -> PromptSchema:
    """Update name, system_prompt, and/or model of an existing prompt."""
    updated = await asyncio.to_thread(
        prompt_repo.update, slug, body.name, body.system_prompt, body.model
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Prompt '{slug}' not found")
    await asyncio.to_thread(db.commit)
    row = await asyncio.to_thread(prompt_repo.get_prompt, slug)
    return PromptSchema(
        slug=row["slug"],
        name=row["name"],
        system_prompt=row["system_prompt"],
        model=row.get("model"),
        is_active=row.get("is_active", True),
    )


@router.patch("/prompts/{slug}/disable", response_model=PromptSchema)
async def disable_prompt(
    slug: str,
    prompt_repo: PromptRepo = Depends(get_prompt_repo),
    db=Depends(get_session),
) -> PromptSchema:
    """Soft-delete a prompt by setting is_active=False."""
    found = await asyncio.to_thread(prompt_repo.set_active, slug, False)
    if not found:
        raise HTTPException(status_code=404, detail=f"Prompt '{slug}' not found")
    await asyncio.to_thread(db.commit)
    row = await asyncio.to_thread(prompt_repo.get_prompt, slug)
    return PromptSchema(
        slug=row["slug"],
        name=row["name"],
        system_prompt=row["system_prompt"],
        model=row.get("model"),
        is_active=row.get("is_active", False),
    )


@router.patch("/prompts/{slug}/enable", response_model=PromptSchema)
async def enable_prompt(
    slug: str,
    prompt_repo: PromptRepo = Depends(get_prompt_repo),
    db=Depends(get_session),
) -> PromptSchema:
    """Re-enable a disabled prompt by setting is_active=True."""
    found = await asyncio.to_thread(prompt_repo.set_active, slug, True)
    if not found:
        raise HTTPException(status_code=404, detail=f"Prompt '{slug}' not found")
    await asyncio.to_thread(db.commit)
    row = await asyncio.to_thread(prompt_repo.get_prompt, slug)
    return PromptSchema(
        slug=row["slug"],
        name=row["name"],
        system_prompt=row["system_prompt"],
        model=row.get("model"),
        is_active=row.get("is_active", True),
    )


@router.delete("/prompts/{slug}", status_code=204)
async def delete_prompt(
    slug: str,
    prompt_repo: PromptRepo = Depends(get_prompt_repo),
    db=Depends(get_session),
) -> None:
    """Hard-delete a prompt. Returns 409 if the prompt has been used in any conversation."""
    used = await asyncio.to_thread(prompt_repo.is_used_in_runs, slug)
    if used:
        raise HTTPException(
            status_code=409, detail="Prompt has been used in conversations"
        )
    deleted = await asyncio.to_thread(prompt_repo.delete, slug)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Prompt '{slug}' not found")
    await asyncio.to_thread(db.commit)
