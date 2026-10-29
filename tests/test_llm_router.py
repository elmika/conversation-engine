"""Tests for RoutingLLMAdapter (dispatch by model slug's provider)."""

from collections.abc import Iterable

from app.application.ports import LLMResult, StreamEvent
from app.infra.llm_router import RoutingLLMAdapter


class FakeLLM:
    """Minimal LLMPort fake that records the model it was called with."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.last_model: str | None = None

    def complete(
        self, instructions: str, messages: list[dict[str, str]], model: str | None = None
    ) -> LLMResult:
        self.last_model = model
        return LLMResult(text=self.name, model=model or "", ttfb_ms=0, total_ms=0)

    def stream(
        self, instructions: str, messages: list[dict[str, str]], model: str | None = None
    ) -> Iterable[StreamEvent]:
        self.last_model = model
        yield StreamEvent(type="final", text=self.name, model=model or "", ttfb_ms=0, total_ms=0)


def test_complete_routes_openai_slug_to_openai_adapter() -> None:
    openai_fake, anthropic_fake = FakeLLM("openai"), FakeLLM("anthropic")
    router = RoutingLLMAdapter(openai_fake, anthropic_fake, default_model="gpt-4.1")

    result = router.complete("instructions", [{"role": "user", "content": "hi"}], model="gpt-4.1")

    assert result["text"] == "openai"
    assert openai_fake.last_model == "gpt-4.1"
    assert anthropic_fake.last_model is None


def test_complete_routes_claude_slug_to_anthropic_adapter() -> None:
    openai_fake, anthropic_fake = FakeLLM("openai"), FakeLLM("anthropic")
    router = RoutingLLMAdapter(openai_fake, anthropic_fake, default_model="gpt-4.1")

    result = router.complete(
        "instructions", [{"role": "user", "content": "hi"}], model="claude-sonnet-5"
    )

    assert result["text"] == "anthropic"
    assert anthropic_fake.last_model == "claude-sonnet-5"
    assert openai_fake.last_model is None


def test_complete_with_no_model_routes_by_default_model_provider() -> None:
    openai_fake, anthropic_fake = FakeLLM("openai"), FakeLLM("anthropic")
    router = RoutingLLMAdapter(openai_fake, anthropic_fake, default_model="claude-haiku-4-5")

    result = router.complete("instructions", [{"role": "user", "content": "hi"}])

    assert result["text"] == "anthropic"
    assert anthropic_fake.last_model == "claude-haiku-4-5"


def test_stream_routes_by_model_slug() -> None:
    openai_fake, anthropic_fake = FakeLLM("openai"), FakeLLM("anthropic")
    router = RoutingLLMAdapter(openai_fake, anthropic_fake, default_model="gpt-4.1")

    events = list(
        router.stream("instructions", [{"role": "user", "content": "hi"}], model="claude-opus-5")
    )

    assert events[0]["text"] == "anthropic"
    assert anthropic_fake.last_model == "claude-opus-5"
