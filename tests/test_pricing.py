"""Tests for USD cost estimation, in particular Anthropic model + snapshot handling."""

from app.domain.pricing import estimate_cost_usd


def test_estimate_cost_for_bare_claude_slug() -> None:
    cost = estimate_cost_usd("claude-sonnet-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 12.00  # $2.00 input + $10.00 output per 1M tokens


def test_estimate_cost_strips_anthropic_dated_snapshot_suffix() -> None:
    """Anthropic echoes back a dated snapshot id (e.g. claude-haiku-4-5-20251001)."""
    cost = estimate_cost_usd(
        "claude-haiku-4-5-20251001", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost == 6.00  # $1.00 input + $5.00 output per 1M tokens


def test_estimate_cost_strips_openai_dated_snapshot_suffix() -> None:
    cost = estimate_cost_usd("gpt-4.1-2025-04-14", input_tokens=1_000_000, output_tokens=0)
    assert cost == 2.00


def test_estimate_cost_returns_none_for_unknown_model() -> None:
    assert estimate_cost_usd("not-a-real-model", input_tokens=100, output_tokens=100) is None
