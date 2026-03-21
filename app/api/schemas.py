"""Request/response schemas for conversation API."""

from typing import Optional

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """Single message in a conversation turn."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ConversationRequest(BaseModel):
    """Request body for creating or extending a conversation."""

    prompt_slug: Optional[str] = None
    model_slug: Optional[str] = None
    messages: list[ConversationMessage] = Field(..., min_length=1)


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


class ConversationRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)


class ConversationRewindRequest(BaseModel):
    message_id: int
    content: str = Field(..., min_length=1)
    prompt_slug: Optional[str] = None
    model_slug: Optional[str] = None


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
    messages: list[MessageSchema]


class PromptSchema(BaseModel):
    slug: str
    name: str
    system_prompt: str
    model: Optional[str] = None


class PromptsResponse(BaseModel):
    prompts: list[PromptSchema]


class ModelSchema(BaseModel):
    slug: str
    name: str
    description: str


class ModelsResponse(BaseModel):
    models: list[ModelSchema]
