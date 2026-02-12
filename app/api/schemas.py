"""Request/response schemas for chat API."""

from typing import Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Single message in a chat request."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    """POST /chat request body."""

    conversation_id: Optional[str] = None
    prompt_slug: Optional[str] = None
    messages: list[ChatMessage] = Field(..., min_length=1)


class TimingsSchema(BaseModel):
    """TTFB and total latency in ms."""

    ttfb_ms: int
    total_ms: int


class ChatResponse(BaseModel):
    """POST /chat response envelope."""

    conversation_id: str
    assistant_message: str
    model: str
    timings: TimingsSchema
