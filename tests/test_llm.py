"""Tests for OpenAI LLM adapter (retry, etc.)."""

from unittest.mock import MagicMock, patch

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
