"""OpenAI Responses API adapter (non-stream for Day 2; stream in Day 3)."""

import time
from typing import Any

from openai import OpenAI

from app.application.ports import LLMResult
from app.settings import Settings


def _build_input_items(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Convert [{role, content}] to Responses API input item list."""
    items = []
    for msg in messages:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        items.append({
            "type": "message",
            "role": role,
            "content": [{"type": "input_text", "text": content}],
        })
    return items


class OpenAILLMAdapter:
    """OpenAI Responses API adapter; uses instructions + input array."""

    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._timeout = settings.request_timeout_s
        self._max_output_tokens = settings.max_output_tokens

    def complete(self, instructions: str, messages: list[dict[str, str]]) -> LLMResult:
        """Run non-streaming completion; return assistant text, model, timings."""
        input_items = _build_input_items(messages)
        if not input_items:
            return LLMResult(
                text="",
                model=self._model,
                ttfb_ms=0,
                total_ms=0,
            )
        start = time.perf_counter()
        response = self._client.responses.create(
            model=self._model,
            instructions=instructions,
            input=input_items,
            max_output_tokens=self._max_output_tokens,
            timeout=self._timeout,
        )
        total_ms = round((time.perf_counter() - start) * 1000)
        text = _extract_output_text(response)
        return LLMResult(
            text=text,
            model=getattr(response, "model", self._model) or self._model,
            ttfb_ms=total_ms,
            total_ms=total_ms,
        )


def _extract_output_text(response: Any) -> str:
    """Extract assistant text from Responses API response object."""
    output = getattr(response, "output", None) or []
    for item in output:
        if getattr(item, "type", None) != "message":
            continue
        content = getattr(item, "content", None) or []
        for block in content:
            if getattr(block, "type", None) == "output_text":
                return getattr(block, "text", None) or ""
    return ""
