"""USD cost estimation for LLM calls, based on a static per-model price table."""

from __future__ import annotations

import re
from typing import Optional

# USD per 1M tokens. Sources: docs/roadmap.md (gpt-4.1, gpt-5.6-luna) and
# benchlm.ai/openai/api-pricing (gpt-5.4-mini, gpt-5.4-nano), confirmed 2026-09-15.
PRICE_PER_MILLION_USD: dict[str, dict[str, float]] = {
    "gpt-4.1": {"input": 2.50, "output": 10.00},
    "gpt-5.6-luna": {"input": 0.20, "output": 1.20},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "gpt-5.4-nano": {"input": 0.20, "output": 1.25},
}

# The OpenAI API often echoes back a dated snapshot id (e.g. "gpt-4.1-2025-04-14")
# in the response instead of the bare alias we requested. Strip that suffix before
# a price-table lookup so a Run recording the snapshot id still prices correctly.
_DATE_SNAPSHOT_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")


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
