"""API routes."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    ConversationListResponse,
    ConversationRenameRequest,
    CompleteSetupResponse,
    ConversationRequest,
    ConversationResponse,
    ConversationRewindRequest,
    ConversationSummary,
    EndSessionResponse,
    InitSessionRequest,
    MessageSchema,
    MessagesResponse,
    ModelSchema,
    ModelsResponse,
    PromptCreateRequest,
    PromptRenderResponse,
    PromptSchema,
    PromptUpdateRequest,
    PromptsResponse,
    SessionSummarySchema,
    TimingsSchema,
)
from app.application.ports import LLMPort, PromptRepo, UnitOfWork
from app.infra.slot_resolver_files import FileSlotResolver
from app.learning.session_summary import build_session_summary
from app.learning.progress_synthesis import synthesise_progress
from app.learning.setup_completion import SetupCompletionError, complete_setup
from app.application.services import ConversationService
from app.domain.model_registry import list_models
from app.domain.prompt_template import PromptTemplateError, validate_template
from app.infra.persistence.db import get_session
from app.infra.persistence.repo_prompt import SQLAlchemyPromptRepo
from app.infra.persistence.unit_of_work import SQLAlchemyUnitOfWork
from app.settings import Settings

# Root router — healthz, models, prompts (no user prefix).
router = APIRouter()

# User-scoped router — all conversation routes live under /u/{user_id}.
user_router = APIRouter(prefix="/u/{user_id}")


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


def get_preview_service(
    uow_factory=Depends(get_uow_factory),
    llm: LLMPort = Depends(get_llm),
    prompt_repo: PromptRepo = Depends(get_prompt_repo),
    settings: Settings = Depends(get_settings),
) -> ConversationService:
    """ConversationService for the prompt preview admin route.

    No user_id needed — slot resolver uses 'default' so this route works
    standalone without any user context.
    """
    return ConversationService(
        uow_factory=uow_factory,
        llm=llm,
        prompt_repo=prompt_repo,
        default_prompt_slug=settings.default_prompt_slug,
        default_model=settings.default_model,
        slot_resolver=FileSlotResolver(settings.sections_dir),
        max_history_turns=settings.max_history_turns,
        max_history_tokens=settings.max_history_tokens,
    )


def get_conversation_service(
    user_id: str = "default",
    uow_factory=Depends(get_uow_factory),
    llm: LLMPort = Depends(get_llm),
    prompt_repo: PromptRepo = Depends(get_prompt_repo),
    settings: Settings = Depends(get_settings),
) -> ConversationService:
    """Provide conversation service with injected dependencies.

    user_id is injected from the path param /u/{user_id} when used under
    user_router; defaults to 'default' for root-level routes (e.g. prompt preview).
    """
    return ConversationService(
        uow_factory=uow_factory,
        llm=llm,
        prompt_repo=prompt_repo,
        default_prompt_slug=settings.default_prompt_slug,
        default_model=settings.default_model,
        slot_resolver=FileSlotResolver(settings.sections_dir, user_id),
        max_history_turns=settings.max_history_turns,
        max_history_tokens=settings.max_history_tokens,
        user_id=user_id,
    )


def _parse_md_h1(content: str) -> Optional[str]:
    """Extract the first H1 heading from markdown content, stripping a 'Course: ' prefix if present."""
    first_line = content.splitlines()[0] if content else ""
    if not first_line.startswith("# "):
        return None
    title = first_line[2:].strip()
    if title.lower().startswith("course: "):
        title = title[8:].strip()
    return title or None


def _check_input_length(messages: list[dict[str, str]], max_chars: int) -> None:
    """Raise 400 if total message content length exceeds max_chars."""
    total = sum(len(m.get("content") or "") for m in messages)
    if total > max_chars:
        raise HTTPException(
            status_code=400,
            detail=f"Total message content length ({total}) exceeds max_input_chars ({max_chars})",
        )


# ── Root routes (no user prefix) ─────────────────────────────────────────────

@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


@router.get("/models", response_model=ModelsResponse)
async def list_models_endpoint() -> ModelsResponse:
    """List all supported models from the model registry."""
    return ModelsResponse(models=[ModelSchema(**m) for m in list_models()])


# ── User-scoped routes (/u/{user_id}/...) ────────────────────────────────────

@user_router.get("/status")
async def get_user_status(
    user_id: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Return whether a learner profile exists for this user_id.

    Response: {"has_profile": bool}
    Frontend uses this to route new users to the setup flow.
    """
    resolver = FileSlotResolver(settings.sections_dir, user_id)
    has_profile = await asyncio.to_thread(resolver.exists, "user")
    return {"has_profile": has_profile}


@user_router.post(
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
            def _stream_setup() -> tuple[str, Any, str, str, UnitOfWork]:
                try:
                    return service.create_and_stream(
                        messages, body.prompt_slug, body.model_slug
                    )
                except ValueError as e:
                    if str(e).startswith("active_conversation_exists"):
                        active_id = str(e).split(":", 1)[1] if ":" in str(e) else None
                        raise HTTPException(status_code=409, detail={"message": "An active conversation already exists", "conversation_id": active_id})
                    raise HTTPException(status_code=400, detail=str(e))

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
                        ev.get("input_tokens", 0),
                        ev.get("output_tokens", 0),
                    )
                    done_payload = {
                        "conversation_id": conv_id,
                        "assistant_message": full_text,
                        "model": model,
                        "timings": {"ttfb_ms": ttfb_ms, "total_ms": total_ms},
                    }
                    yield _sse_event("done", done_payload)
        except HTTPException as exc:
            yield _sse_http_error(exc)
        except Exception:
            yield _sse_event("done", {"error": {"type": "internal_error", "message": "An unexpected error occurred during streaming"}})
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@user_router.post(
    "/conversations/init-stream",
    name="init_session_stream",
)
async def init_session_stream(
    user_id: str,
    body: InitSessionRequest = Body(default_factory=InitSessionRequest),
    service: ConversationService = Depends(get_conversation_service),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """
    Create a new conversation and stream an AI-initiated opening message.

    The LLM opens the session with a course recap and progress summary.
    No user message is stored — only the assistant's opening message lands in the conversation.

    Emits SSE events:
      - meta: conversation_id, model, prompt_slug
      - chunk: incremental text delta
      - done: final assistant message + timings
    """
    # Resolve conversation name from course content (L2 concern, lives here until L2 layer exists).
    # Skip for setup conversations — the user has no course file yet.
    requested_slug = body.prompt_slug or "course-session-init"
    course_content = FileSlotResolver(settings.sections_dir, user_id).resolve("course")
    conv_name = _parse_md_h1(course_content) if course_content else None

    async def event_generator() -> AsyncIterator[str]:
        try:
            def _stream_setup() -> tuple[str, Any, str, str, UnitOfWork]:
                try:
                    return service.create_and_stream_init(
                        requested_slug, body.model_slug, name=conv_name
                    )
                except ValueError as e:
                    if str(e).startswith("active_conversation_exists"):
                        active_id = str(e).split(":", 1)[1] if ":" in str(e) else None
                        raise HTTPException(status_code=409, detail={"message": "An active conversation already exists", "conversation_id": active_id})
                    raise HTTPException(status_code=400, detail=str(e))

            conv_id, events, used_prompt_slug, resolved_model, uow = await asyncio.to_thread(
                _stream_setup
            )

            yield _sse_event("meta", {
                "conversation_id": conv_id,
                "model": resolved_model,
                "prompt_slug": used_prompt_slug,
            })

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
                        ev.get("input_tokens", 0),
                        ev.get("output_tokens", 0),
                    )
                    yield _sse_event("done", {
                        "conversation_id": conv_id,
                        "assistant_message": full_text,
                        "model": model,
                        "timings": {"ttfb_ms": ttfb_ms, "total_ms": total_ms},
                    })
                elif ev.get("type") == "error":
                    yield _sse_event("done", {"error": ev.get("error_message", "Stream error")})
        except HTTPException as exc:
            yield _sse_http_error(exc)
        except Exception:
            yield _sse_event("done", {"error": {"type": "internal_error", "message": "An unexpected error occurred"}})
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@user_router.post("/conversations", name="create_conversation", response_model=ConversationResponse)
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
        if str(e).startswith("active_conversation_exists"):
            active_id = str(e).split(":", 1)[1] if ":" in str(e) else None
            raise HTTPException(status_code=409, detail={"message": "An active conversation already exists", "conversation_id": active_id})
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


def _sse_http_error(exc: HTTPException) -> str:
    """Format an HTTPException as a terminal SSE done error event."""
    detail = exc.detail
    msg = detail.get("message", str(detail)) if isinstance(detail, dict) else str(detail)
    error: dict[str, Any] = {"type": "http_error", "status_code": exc.status_code, "message": msg}
    if exc.status_code == 409 and isinstance(detail, dict) and detail.get("conversation_id"):
        error["conversation_id"] = detail["conversation_id"]
    return _sse_event("done", {"error": error})


@user_router.post(
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
        except PromptTemplateError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ValueError as e:
            if str(e) == "conversation_ended":
                raise HTTPException(status_code=409, detail="Conversation has ended")
            raise HTTPException(status_code=404, detail=str(e))

    conv_id, assistant_message, model, ttfb_ms, total_ms = await asyncio.to_thread(_run)
    return ConversationResponse(
        conversation_id=conv_id,
        assistant_message=assistant_message,
        model=model,
        timings=TimingsSchema(ttfb_ms=ttfb_ms, total_ms=total_ms),
    )


@user_router.post(
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
                except PromptTemplateError as e:
                    raise HTTPException(status_code=400, detail=str(e))
                except ValueError as e:
                    if str(e) == "conversation_ended":
                        raise HTTPException(status_code=409, detail="Conversation has ended")
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
                        ev.get("input_tokens", 0),
                        ev.get("output_tokens", 0),
                    )
                    done_payload = {
                        "conversation_id": conv_id,
                        "assistant_message": full_text,
                        "model": model,
                        "timings": {"ttfb_ms": ttfb_ms, "total_ms": total_ms},
                    }
                    yield _sse_event("done", done_payload)
        except HTTPException as exc:
            yield _sse_http_error(exc)
        except Exception:
            yield _sse_event("done", {"error": {"type": "internal_error", "message": "An unexpected error occurred during streaming"}})
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@user_router.post(
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
                except PromptTemplateError as e:
                    raise HTTPException(status_code=400, detail=str(e))
                except ValueError as e:
                    if str(e) == "conversation_ended":
                        raise HTTPException(status_code=409, detail="Conversation has ended")
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
                        ev.get("input_tokens", 0),
                        ev.get("output_tokens", 0),
                    )
                    done_payload = {
                        "conversation_id": conv_id,
                        "assistant_message": full_text,
                        "model": model,
                        "timings": {"ttfb_ms": ttfb_ms, "total_ms": total_ms},
                    }
                    yield _sse_event("done", done_payload)
        except HTTPException as exc:
            yield _sse_http_error(exc)
        except Exception:
            yield _sse_event("done", {"error": {"type": "internal_error", "message": "An unexpected error occurred during streaming"}})
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@user_router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    uow_factory=Depends(get_uow_factory),
) -> ConversationListResponse:
    """List conversations for user_id with pagination, ordered by created_at DESC."""
    def _run() -> tuple[list[dict], int]:
        with uow_factory() as uow:
            return uow.repo.list_conversations(user_id, page, page_size)

    rows, total = await asyncio.to_thread(_run)
    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                id=r["id"],
                name=r.get("name"),
                created_at=r["created_at"],
                last_activity=r.get("last_activity"),
                first_message=r.get("first_message"),
                ended_at=r.get("ended_at"),
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@user_router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    user_id: str,
    conversation_id: str,
    uow_factory=Depends(get_uow_factory),
) -> None:
    """Delete a conversation and all its messages. No-op if not owned by user_id."""
    def _run() -> None:
        with uow_factory() as uow:
            uow.repo.delete_conversation(conversation_id, user_id)
            uow.commit()

    await asyncio.to_thread(_run)


@user_router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
async def rename_conversation(
    user_id: str,
    conversation_id: str,
    body: ConversationRenameRequest,
    uow_factory=Depends(get_uow_factory),
) -> ConversationSummary:
    """Rename a conversation. Returns 404 if not found or not owned by user_id."""
    def _run() -> None:
        with uow_factory() as uow:
            if uow.repo.get_conversation(conversation_id, user_id) is None:
                raise HTTPException(status_code=404, detail="Conversation not found")
            uow.repo.rename_conversation(conversation_id, body.name, user_id)
            uow.commit()

    await asyncio.to_thread(_run)
    return ConversationSummary(id=conversation_id, name=body.name, created_at="")


@user_router.get("/conversations/{conversation_id}/messages", response_model=MessagesResponse)
async def get_conversation_messages(
    user_id: str,
    conversation_id: str,
    uow_factory=Depends(get_uow_factory),
) -> MessagesResponse:
    """Get all messages for a conversation, ordered by id ASC. Returns 404 if not owned by user_id."""
    def _run() -> tuple[list[dict], Optional[dict]]:
        with uow_factory() as uow:
            conv = uow.repo.get_conversation(conversation_id, user_id)
            if conv is None:
                raise HTTPException(status_code=404, detail="Conversation not found")
            msgs = uow.repo.get_messages_with_metadata(conversation_id, user_id)
            return msgs, conv

    msgs, conv = await asyncio.to_thread(_run)
    return MessagesResponse(
        conversation_id=conversation_id,
        ended_at=conv["ended_at"] if conv else None,
        prompt_slug=conv["prompt_slug"] if conv else None,
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


@user_router.post(
    "/conversations/{conversation_id}/end-session",
    response_model=EndSessionResponse,
)
async def end_session(
    user_id: str,
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
    settings: Settings = Depends(get_settings),
    llm: LLMPort = Depends(get_llm),
) -> EndSessionResponse:
    """
    End a conversation session.

    Marks the conversation as ended, runs progress synthesis synchronously, then
    returns the updated session summary. Synthesis is synchronous so the summary
    always reflects the completed session — the learner sees the correct next step
    immediately. Returns 409 if the conversation is already ended.
    """
    def _end() -> list[dict]:
        try:
            return service.end_conversation(conversation_id)
        except ValueError as e:
            if str(e) == "conversation_ended":
                raise HTTPException(status_code=409, detail="Conversation has already ended")
            raise HTTPException(status_code=404, detail=str(e))

    messages = await asyncio.to_thread(_end)
    await asyncio.to_thread(
        synthesise_progress,
        messages,
        FileSlotResolver(settings.sections_dir, user_id),
        llm,
        settings.sections_dir,
        settings.wrap_up_model,
        user_id,
    )
    summary_data = await asyncio.to_thread(
        build_session_summary, FileSlotResolver(settings.sections_dir, user_id)
    )
    return EndSessionResponse(status="ended", summary=SessionSummarySchema(**summary_data))


@user_router.post(
    "/conversations/{conversation_id}/complete-setup",
    response_model=CompleteSetupResponse,
)
async def complete_setup_route(
    user_id: str,
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
    settings: Settings = Depends(get_settings),
    llm: LLMPort = Depends(get_llm),
    prompt_repo: PromptRepo = Depends(get_prompt_repo),
) -> CompleteSetupResponse:
    """
    Complete the setup flow: run profile + outline extraction, write section files,
    and mark the conversation ended.

    SYNCHRONOUS by design — the learner is blocked on this before the first course
    session can begin, and follow-up prompts require sections/user/<user_id>.md
    and sections/course/<user_id>.md to exist. Two extraction LLM calls run before
    the response returns. Returns 409 if the conversation is already ended.

    Ordering matters: extraction + file writes run FIRST, and the conversation is
    ended LAST. If extraction/writes fail, the conversation stays active and the
    learner can retry — nothing is left half-finished.
    """
    def _load_messages() -> list[dict]:
        try:
            return service.get_active_messages(conversation_id)
        except ValueError as e:
            if str(e) == "conversation_ended":
                raise HTTPException(status_code=409, detail="Conversation has already ended")
            raise HTTPException(status_code=404, detail=str(e))

    messages = await asyncio.to_thread(_load_messages)

    try:
        await asyncio.to_thread(
            complete_setup,
            messages,
            prompt_repo,
            llm,
            settings.sections_dir,
            user_id,
        )
    except SetupCompletionError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Profile + course files are now durably written — safe to end the conversation.
    def _end() -> None:
        try:
            service.end_conversation(conversation_id)
        except ValueError as e:
            if str(e) == "conversation_ended":
                raise HTTPException(status_code=409, detail="Conversation has already ended")
            raise HTTPException(status_code=404, detail=str(e))

    await asyncio.to_thread(_end)

    return CompleteSetupResponse(status="completed")


@user_router.get(
    "/conversations/{conversation_id}/summary",
    response_model=SessionSummarySchema,
)
async def get_session_summary(
    user_id: str,
    conversation_id: str,
    uow_factory=Depends(get_uow_factory),
    settings: Settings = Depends(get_settings),
) -> SessionSummarySchema:
    """Return the session summary for an ended conversation."""
    def _check() -> None:
        with uow_factory() as uow:
            conv = uow.repo.get_conversation(conversation_id, user_id)
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")
            if not conv["ended_at"]:
                raise HTTPException(status_code=409, detail="Conversation has not ended")

    await asyncio.to_thread(_check)
    summary_data = await asyncio.to_thread(
        build_session_summary, FileSlotResolver(settings.sections_dir, user_id)
    )
    return SessionSummarySchema(**summary_data)


# ── Prompt admin routes (root, no user prefix) ────────────────────────────────

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
        validate_template(body.system_prompt)
    except PromptTemplateError as e:
        raise HTTPException(status_code=400, detail=str(e))
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


@router.get("/prompts/{slug}/render", response_model=PromptRenderResponse)
async def render_prompt_preview(
    slug: str,
    conversation_id: Optional[str] = None,
    service: ConversationService = Depends(get_preview_service),
) -> PromptRenderResponse:
    """Return the prompt's system_prompt with all template variables resolved.

    Pass ?conversation_id= to anchor time:conversation-start and
    time:lesson-time-spent to a specific conversation's start time.
    """
    def _run() -> dict:
        try:
            return service.preview_prompt(slug, conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    result = await asyncio.to_thread(_run)
    return PromptRenderResponse(**result)


@router.put("/prompts/{slug}", response_model=PromptSchema)
async def update_prompt(
    slug: str,
    body: PromptUpdateRequest,
    prompt_repo: PromptRepo = Depends(get_prompt_repo),
    db=Depends(get_session),
) -> PromptSchema:
    """Update name, system_prompt, and/or model of an existing prompt."""
    try:
        validate_template(body.system_prompt)
    except PromptTemplateError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
