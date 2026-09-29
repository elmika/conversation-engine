"""USD cost estimation for LLM calls, based on a static per-model price table."""

from __future__ import annotations

import re
from typing import Optional

# USD per 1M tokens (short-context, non-batch, standard tier — no cached-input or
# cache-write discount applied). Source: https://developers.openai.com/api/docs/pricing
# and per-model pages, confirmed live 2026-09-17. gpt-4.1 dropped from $2.50/$10.00
# (the price recorded 2026-09-15) to $2.00/$8.00 since the last check — always
# re-confirm against the live pricing page rather than trusting this comment's date.
PRICE_PER_MILLION_USD: dict[str, dict[str, float]] = {
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-5.4": {"input": 2.50, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "gpt-5.4-nano": {"input": 0.20, "output": 1.25},
    "gpt-5.4-pro": {"input": 30.00, "output": 180.00},
    "gpt-5.5": {"input": 5.00, "output": 30.00},
    "gpt-5.6-luna": {"input": 0.20, "output": 1.20},
    "gpt-5.6-terra": {"input": 2.00, "output": 12.00},
    "gpt-5.6-sol": {"input": 4.00, "output": 20.00},
    "gpt-6-astra": {"input": 10.00, "output": 50.00},

    # Anthropic — https://www.anthropic.com/pricing, confirmed 2026-09-29.
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
}

# The OpenAI API often echoes back a dated snapshot id (e.g. "gpt-4.1-2025-04-14")
# in the response instead of the bare alias we requested; Anthropic does the same
# with a different date format (e.g. "claude-haiku-4-5-20251001"). Strip either
# suffix before a price-table lookup so a Run recording the snapshot id still
# prices correctly.
_DATE_SNAPSHOT_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$|-\d{8}$")


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """Estimate the USD cost of a single LLM call.

    Returns None if the model has no price-table entry — the caller must fail closed
    on None rather than silently treating an unpriced model as free.
    """
    prices = PRICE_PER_MILLION_USD.get(model)
    if prices is None:
        prices = PRICE_PER_MILLION_USD.get(_DATE_SNAPSHOT_SUFFIX.sub("", model))
    if prices is None:
        return None
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000
