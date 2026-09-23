"""Request/response schemas for conversation API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """Single message in a conversation turn."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ConversationRequest(BaseModel):
    """Request body for creating or extending a conversation (learner-facing).

    No prompt_slug/model_slug here on purpose — which prompt drives a turn and
    which model answers it are code-owned decisions (see CLAUDE.md "Layer
    model" / the lesson & setup flow orchestrators), never learner input.
    Admin/test tooling that needs to override either uses the mirrored
    Admin* request models on the /admin/u/{user_id}/... routes instead.
    """

    messages: list[ConversationMessage] = Field(..., min_length=1)


class InitSessionRequest(BaseModel):
    """Request body for AI-initiated session opening (learner-facing).

    Empty on purpose: which flow opens (setup vs. course session) is derived
    server-side from the learner's profile state, never client input. See
    ConversationRequest's docstring.
    """


class AdminConversationRequest(BaseModel):
    """Request body for creating/extending a conversation via /admin/u/{user_id}/...

    Unlike ConversationRequest, this legitimately accepts prompt_slug/model_slug
    overrides — used by internal test/comparison tooling (e.g.
    scripts/compare_outline_models.py) that needs to drive a specific prompt or
    model through the real flow. Gated by require_admin at the route level.
    """

    prompt_slug: Optional[str] = None
    model_slug: Optional[str] = None
    messages: list[ConversationMessage] = Field(..., min_length=1)


class AdminInitSessionRequest(BaseModel):
    """Request body for AI-initiated session opening via /admin/u/{user_id}/...

    See AdminConversationRequest's docstring.
    """

    prompt_slug: Optional[str] = None
    model_slug: Optional[str] = None


class TimingsSchema(BaseModel):
    """TTFB and total latency in ms."""

    ttfb_ms: int
    total_ms: int


class ConversationResponse(BaseModel):
    """Response envelope for a conversation turn."""

    conversation_id: str
    assistant_message: str
    model: str
    timings: TimingsSchema


class ConversationSummary(BaseModel):
    id: str
    name: Optional[str] = None
    created_at: str  # ISO 8601
    last_activity: Optional[str] = None
    first_message: Optional[str] = None
    ended_at: Optional[str] = None  # ISO 8601; None means still active
    user_id: Optional[str] = None  # populated only by admin cross-user listing


class ConversationRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)


class ConversationRewindRequest(BaseModel):
    """No prompt_slug/model_slug — see ConversationRequest's docstring."""

    message_id: int
    content: str = Field(..., min_length=1)


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]
    total: int
    page: int
    page_size: int


class MessageSchema(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class MessagesResponse(BaseModel):
    conversation_id: str
    ended_at: Optional[str] = None  # ISO 8601; None means still active
    prompt_slug: Optional[str] = None  # course/prompt locked in at conversation creation
    messages: list[MessageSchema]


class SessionSummaryModuleSchema(BaseModel):
    title: str
    status: Optional[Literal["done", "current", "upcoming"]] = None


class SessionSummarySchema(BaseModel):
    course_name: Optional[str] = None
    modules: list[SessionSummaryModuleSchema] = []
    next_step: Optional[str] = None


class EndSessionResponse(BaseModel):
    status: str = "ended"
    summary: Optional[SessionSummarySchema] = None


class CompleteSetupResponse(BaseModel):
    status: str = "completed"


class ConsentStatusResponse(BaseModel):
    consented: bool
    consented_at: Optional[datetime] = None


class ConsentRecordResponse(BaseModel):
    status: str = "recorded"
    consented_at: datetime


class PromptSchema(BaseModel):
    slug: str
    name: str
    system_prompt: str
    model: Optional[str] = None
    is_active: bool = True


class PromptCreateRequest(BaseModel):
    slug: str = Field(..., pattern=r"^[a-z0-9][a-z0-9\-_]*$", max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    system_prompt: str = Field(..., min_length=1)
    model: Optional[str] = None


class PromptUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    system_prompt: str = Field(..., min_length=1)
    model: Optional[str] = None


class PromptsResponse(BaseModel):
    prompts: list[PromptSchema]


class ModelSchema(BaseModel):
    slug: str
    name: str
    description: str


class ModelsResponse(BaseModel):
    models: list[ModelSchema]


class PromptRenderResponse(BaseModel):
    slug: str
    name: str
    rendered_prompt: str


class UserUsageSchema(BaseModel):
    user_id: str
    usd_today: float


class UsageTodayResponse(BaseModel):
    platform_usd_today: float
    by_user: list[UserUsageSchema]
