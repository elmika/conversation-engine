"""Tests for Anthropic LLM adapter (retry + error mapping)."""

from unittest.mock import MagicMock, patch

import pytest
from anthropic import APIConnectionError, APITimeoutError, BadRequestError, RateLimitError
from fastapi import HTTPException

from app.infra.llm_anthropic import AnthropicLLMAdapter
from app.settings import Settings


def test_adapter_retries_on_rate_limit_then_succeeds() -> None:
    """complete() retries on RateLimitError and returns result on second attempt."""
    block = MagicMock(type="text", text="ok")
    mock_response = MagicMock(content=[block], model="claude-sonnet-5")

    rate_limit = RateLimitError("rate limit", response=MagicMock(), body=MagicMock())
    mock_create = MagicMock(side_effect=[rate_limit, mock_response])

    settings = Settings(max_retries=2, retry_backoff_s=0.01)
    with patch("app.infra.llm_anthropic.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_anthropic_class.return_value = mock_client

        adapter = AnthropicLLMAdapter(settings)
        result = adapter.complete("instructions", [{"role": "user", "content": "hi"}])

    assert result["text"] == "ok"
    assert mock_create.call_count == 2


def test_adapter_builds_messages_payload_shape() -> None:
    """complete() should build the Messages API system + messages payload."""
    block = MagicMock(type="text", text="ok")
    mock_response = MagicMock(content=[block], model="claude-sonnet-5")

    settings = Settings(max_retries=0, retry_backoff_s=0.0)
    with patch("app.infra.llm_anthropic.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        adapter = AnthropicLLMAdapter(settings)
        adapter.complete(
            "instructions",
            [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
                {"role": "user", "content": "Bye"},
            ],
        )

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["system"] == "instructions"
    assert kwargs["messages"] == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
        {"role": "user", "content": "Bye"},
    ]


def _make_adapter_with_exception(exc: Exception) -> AnthropicLLMAdapter:
    """Create an adapter whose client always raises the given exception."""
    settings = Settings(max_retries=0, retry_backoff_s=0.0)
    with patch("app.infra.llm_anthropic.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = exc
        mock_anthropic_class.return_value = mock_client
        return AnthropicLLMAdapter(settings)


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (RateLimitError("rate limit", response=MagicMock(), body=MagicMock()), 429),
        (APITimeoutError(request=MagicMock()), 504),
        (APIConnectionError(request=MagicMock()), 502),
        (
            BadRequestError(
                "bad request",
                response=MagicMock(),
                body={"error": {"message": "invalid", "type": "invalid_request_error"}},
            ),
            502,
        ),
    ],
)
def test_adapter_maps_anthropic_errors_to_http_exception(
    exc: Exception, expected_status: int
) -> None:
    adapter = _make_adapter_with_exception(exc)
    with pytest.raises(HTTPException) as ctx:
        adapter.complete("instructions", [{"role": "user", "content": "hi"}])
    assert ctx.value.status_code == expected_status
