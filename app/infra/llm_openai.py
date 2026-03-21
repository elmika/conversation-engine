"""OpenAI Responses API adapter (non-stream + stream)."""

import logging
import time
from collections.abc import Iterable
from typing import Any

from fastapi import HTTPException, status
from openai import (
    APIConnectionError,
    APITimeoutError,
    APIError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from app.application.ports import LLMResult, StreamEvent
from app.settings import Settings

logger = logging.getLogger(__name__)

# Transient errors we retry with backoff before mapping to HTTP errors.
RETRYABLE_EXCEPTIONS = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)


def _map_openai_error(exc: Exception) -> HTTPException:
    """Map known OpenAI errors to HTTP errors without leaking prompt content."""
    if isinstance(exc, RateLimitError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upstream OpenAI rate limit exceeded. Please retry later.",
        )
    if isinstance(exc, APITimeoutError):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream OpenAI request timed out.",
        )
    if isinstance(exc, APIConnectionError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach upstream OpenAI service.",
        )
    if isinstance(exc, InternalServerError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream OpenAI service returned an internal error.",
        )
    if isinstance(exc, APIError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream OpenAI API error.",
        )
    # Fallback: unknown error type, treat as generic upstream failure.
    return HTTPException(status_code=status.HTTP_BAD_GATEWAY, detail="Upstream error.")


def _build_input_items(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Convert [{role, content}] to Responses API input item list.

    Content type is role-based: user/system messages use "input_text";
    assistant messages (prior model output in history) use "output_text".
    See Responses API docs; mismatch causes 400 on append (input[1].content[0]).
    """
    items: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        # User and system are inputs; assistant is model output.
        content_type = "output_text" if role == "assistant" else "input_text"
        items.append(
            {
                "type": "message",
                "role": role,
                "content": [{"type": content_type, "text": content}],
            }
        )
    return items


class OpenAILLMAdapter:
    """OpenAI Responses API adapter; uses instructions + input array."""

    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._timeout = settings.request_timeout_s
        self._max_output_tokens = settings.max_output_tokens
        self._max_retries = settings.max_retries
        self._retry_backoff_s = settings.retry_backoff_s

    def complete(
        self,
        instructions: str,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> LLMResult:
        """Run non-streaming completion; return assistant text, model, timings.

        If model is provided it overrides the adapter's configured default.
        """
        effective_model = model or self._model
        input_items = _build_input_items(messages)
        if not input_items:
            return LLMResult(
                text="",
                model=effective_model,
                ttfb_ms=0,
                total_ms=0,
            )
        last_exc: Exception | None = None
        try:
            for attempt in range(self._max_retries + 1):
                try:
                    start = time.perf_counter()
                    response = self._client.responses.create(
                        model=effective_model,
                        instructions=instructions,
                        input=input_items,
                        max_output_tokens=self._max_output_tokens,
                        timeout=self._timeout,
                    )
                    total_ms = round((time.perf_counter() - start) * 1000)
                    text = _extract_output_text(response)
                    return LLMResult(
                        text=text,
                        model=getattr(response, "model", effective_model) or effective_model,
                        ttfb_ms=total_ms,
                        total_ms=total_ms,
                    )
                except RETRYABLE_EXCEPTIONS as exc:
                    last_exc = exc
                    if attempt < self._max_retries:
                        delay = self._retry_backoff_s * (2**attempt)
                        logger.warning(
                            "OpenAI request failed (attempt %s/%s), retrying in %.1fs (%s)",
                            attempt + 1,
                            self._max_retries + 1,
                            delay,
                            exc.__class__.__name__,
                        )
                        time.sleep(delay)
                    else:
                        raise _map_openai_error(exc)
        except APIError as exc:
            # Non-retryable OpenAI API errors (e.g. BadRequestError) should be
            # mapped to HTTP errors rather than bubbling up as 500s.
            raise _map_openai_error(exc)
        # Should never be reached, but keep mypy happy.
        raise _map_openai_error(last_exc or Exception("Unknown OpenAI error"))

    def stream(
        self,
        instructions: str,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> Iterable[StreamEvent]:
        """
        Run streaming completion; yield StreamEvent items.

        If model is provided it overrides the adapter's configured default.
        TTFB is measured as time until first text delta; total_ms until final response.
        """
        effective_model = model or self._model
        input_items = _build_input_items(messages)
        if not input_items:
            return []

        last_exc: Exception | None = None
        try:
            for attempt in range(self._max_retries + 1):
                try:
                    yield from self._stream_once(instructions, input_items, effective_model)
                    return
                except RETRYABLE_EXCEPTIONS as exc:
                    last_exc = exc
                    if attempt < self._max_retries:
                        delay = self._retry_backoff_s * (2**attempt)
                        logger.warning(
                            "OpenAI stream failed (attempt %s/%s), retrying in %.1fs (%s)",
                            attempt + 1,
                            self._max_retries + 1,
                            delay,
                            exc.__class__.__name__,
                        )
                        time.sleep(delay)
                    else:
                        raise _map_openai_error(exc)
        except APIError as exc:
            # Non-retryable OpenAI API errors during streaming should also be
            # mapped consistently to HTTP errors.
            raise _map_openai_error(exc)
        # Should never be reached, but keep mypy happy.
        raise _map_openai_error(last_exc or Exception("Unknown OpenAI error"))

    def _stream_once(
        self, instructions: str, input_items: list[dict[str, Any]], effective_model: str
    ) -> Iterable[StreamEvent]:
        """Single attempt at streaming; used by stream() with retry wrapper."""
        start = time.perf_counter()
        first_delta_ms = 0

        with self._client.responses.stream(
            model=effective_model,
            instructions=instructions,
            input=input_items,
            max_output_tokens=self._max_output_tokens,
            timeout=self._timeout,
        ) as stream:
            for event in stream:
                if getattr(event, "type", None) == "response.output_text.delta":
                    if not first_delta_ms:
                        first_delta_ms = round((time.perf_counter() - start) * 1000)
                    delta = getattr(event, "delta", "") or ""
                    if not delta:
                        continue
                    yield StreamEvent(
                        type="delta",
                        delta=delta,
                        model=effective_model,
                        ttfb_ms=first_delta_ms,
                        total_ms=0,
                    )
            final_response = stream.get_final_response()

        total_ms = round((time.perf_counter() - start) * 1000)
        text = _extract_output_text(final_response)
        resolved_model = getattr(final_response, "model", effective_model) or effective_model
        yield StreamEvent(
            type="final",
            text=text,
            model=resolved_model,
            ttfb_ms=first_delta_ms or total_ms,
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
