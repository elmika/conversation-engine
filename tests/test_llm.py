"""Tests for OpenAI LLM adapter (retry + error mapping)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from openai import APIConnectionError, APITimeoutError, BadRequestError, RateLimitError

from app.infra.llm_openai import OpenAILLMAdapter
from app.settings import Settings


def test_adapter_retries_on_rate_limit_then_succeeds() -> None:
    """complete() retries on RateLimitError and returns result on second attempt."""
    from openai import RateLimitError

    # Mock response that _extract_output_text can read.
    block = MagicMock(type="output_text", text="ok")
    item = MagicMock(type="message", content=[block])
    mock_response = MagicMock(output=[item], model="gpt-4.1-mini")

    rate_limit = RateLimitError("rate limit", response=MagicMock(), body=MagicMock())
    mock_create = MagicMock(side_effect=[rate_limit, mock_response])

    settings = Settings(max_retries=2, retry_backoff_s=0.01)
    with patch("app.infra.llm_openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_client.responses.create = mock_create
        mock_openai_class.return_value = mock_client

        adapter = OpenAILLMAdapter(settings)
        result = adapter.complete("instructions", [{"role": "user", "content": "hi"}])

    assert result["text"] == "ok"
    assert mock_create.call_count == 2


def test_adapter_builds_responses_input_payload_shape() -> None:
    """
    complete() should build Responses API `input` items with the correct shape.

    This test documents the expected schema for text inputs, and will fail as
    long as _build_input_items constructs a payload that does not match it
    (e.g. wrong content[type] value), which is currently causing upstream
    400 Bad Request errors.
    """
    # Arrange a minimal successful Responses object so complete() can finish.
    block = MagicMock(type="output_text", text="ok")
    item = MagicMock(type="message", content=[block])
    mock_response = MagicMock(output=[item], model="gpt-4.1-mini")

    settings = Settings(max_retries=0, retry_backoff_s=0.0)
    with patch("app.infra.llm_openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_client.responses.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        adapter = OpenAILLMAdapter(settings)
        adapter.complete("instructions", [{"role": "user", "content": "Hi"}])

    # Assert: the payload we send to Responses matches the expected schema.
    kwargs = mock_client.responses.create.call_args.kwargs
    input_items = kwargs["input"]
    assert isinstance(input_items, list)
    assert input_items, "input items should not be empty"

    first = input_items[0]
    assert first["type"] == "message"
    assert first["role"] == "user"
    assert isinstance(first["content"], list)
    assert first["content"], "message content list should not be empty"

    content0 = first["content"][0]
    # Expected behaviour (will currently FAIL): content type should be
    # the correct Responses API text content type, not the value that is
    # currently rejected upstream with:
    #   Invalid value: 'input_text'. Supported values are: 'output_text' and 'refusal'.
    assert content0["type"] == "output_text"
    assert content0["text"] == "Hi"


def _make_adapter_with_exception(exc: Exception) -> OpenAILLMAdapter:
    """Create an adapter whose client always raises the given exception."""
    settings = Settings(max_retries=0, retry_backoff_s=0.0)
    with patch("app.infra.llm_openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_client.responses.create.side_effect = exc
        mock_openai_class.return_value = mock_client
        return OpenAILLMAdapter(settings)


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (RateLimitError("rate limit", response=MagicMock(), body=MagicMock()), 429),
        # For these HTTPX-based errors, a simple message argument is enough; we
        # don't need to construct a real httpx.Request instance for the test.
        (APITimeoutError("timeout"), 504),
        # APIConnectionError in the current SDK version requires a keyword-only
        # `request` argument; we can satisfy it with a simple MagicMock.
        (APIConnectionError(request=MagicMock()), 502),
        # Non-retryable invalid request from OpenAI (e.g. bad input payload).
        # We expect this to be surfaced as a 502 "Upstream OpenAI API error."
        # via _map_openai_error(), not as an unhandled 500.
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
def test_adapter_maps_openai_errors_to_http_exception(
    exc: Exception, expected_status: int
) -> None:
    adapter = _make_adapter_with_exception(exc)
    with pytest.raises(HTTPException) as ctx:
        adapter.complete("instructions", [{"role": "user", "content": "hi"}])
    assert ctx.value.status_code == expected_status
