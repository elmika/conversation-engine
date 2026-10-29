"""Routes LLMPort calls to the right provider adapter by model slug."""

from collections.abc import Iterable

from app.application.ports import LLMPort, LLMResult, StreamEvent
from app.domain.model_registry import get_model


class RoutingLLMAdapter:
    """LLMPort that dispatches each call to the adapter matching the model's provider.

    Callers (ConversationService, routes.py) keep depending on a single
    LLMPort, unaware that more than one provider exists behind it — the
    same seam OpenAILLMAdapter/AnthropicLLMAdapter each already satisfy on
    their own.
    """

    def __init__(
        self,
        openai_adapter: LLMPort,
        anthropic_adapter: LLMPort,
        default_model: str,
    ) -> None:
        self._adapters: dict[str, LLMPort] = {
            "openai": openai_adapter,
            "anthropic": anthropic_adapter,
        }
        self._default_model = default_model

    def _resolve(self, model: str | None) -> tuple[LLMPort, str]:
        effective_model = model or self._default_model
        provider = get_model(effective_model)["provider"]
        return self._adapters[provider], effective_model

    def complete(
        self,
        instructions: str,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> LLMResult:
        adapter, effective_model = self._resolve(model)
        return adapter.complete(instructions, messages, model=effective_model)

    def stream(
        self,
        instructions: str,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> Iterable[StreamEvent]:
        adapter, effective_model = self._resolve(model)
        return adapter.stream(instructions, messages, model=effective_model)
