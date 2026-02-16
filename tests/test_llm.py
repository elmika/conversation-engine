"""Tests for OpenAI LLM adapter (retry + error mapping)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from openai import APIConnectionError, APITimeoutError, RateLimitError

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
        (APITimeoutError("timeout", request=MagicMock()), 504),
        (APIConnectionError("conn", request=MagicMock()), 502),
    ],
)
def test_adapter_maps_openai_errors_to_http_exception(
    exc: Exception, expected_status: int
) -> None:
    adapter = _make_adapter_with_exception(exc)
    with pytest.raises(HTTPException) as ctx:
        adapter.complete("instructions", [{"role": "user", "content": "hi"}])
    assert ctx.value.status_code == expected_status
