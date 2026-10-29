#!/usr/bin/env python3
"""List provider models this repo doesn't know about yet — the "re-check GET /v1/models
first" step in docs/model-decisions.md, scripted.

Diffs each provider's live `GET /v1/models` (free, no tokens) against
app/domain/model_registry.py and app/domain/pricing.py and reports:
  - NEW       — served by the provider, not in MODELS (comparison candidates)
  - UNPRICED  — in MODELS but missing from PRICE_PER_MILLION_USD
  - GONE      — in MODELS but no longer served (retired — any prompt pinned to it will fail)

Neither provider's API exposes prices, so this can't fill them in: NEW/UNPRICED entries
still need a manual look at the pricing pages printed at the end, before the model is
added to both files (see "How to run the next comparison" in docs/model-decisions.md).

Noise is filtered out: NEW only lists releases from the last 180 days (legacy models the
provider still serves aren't candidates), dated snapshot ids whose alias also exists (or is
registered), and OpenAI's non-text families (image, audio, realtime, embeddings, …) that
LLMPort can't call anyway. --since YYYY-MM-DD moves the cutoff; --all disables all filtering.

Stdlib-only, matching every other hand-run script in scripts/.

Usage:
  python3 scripts/check_new_models.py               # or: make check-models
  python3 scripts/check_new_models.py --since 2026-09-01
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_api_keys import load_env_value  # noqa: E402

from app.domain.model_registry import MODELS  # noqa: E402
from app.domain.pricing import PRICE_PER_MILLION_USD  # noqa: E402

PRICING_PAGES = {
    "openai": "https://developers.openai.com/api/docs/pricing",
    # API prices — anthropic.com/pricing only lists consumer plans.
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
}

# OpenAI model families LLMPort can't use (it drives text chat via the Responses API).
_OPENAI_NON_TEXT = re.compile(
    r"(image|dall-e|tts|whisper|transcribe|audio|realtime|embedding|moderation|"
    r"search|live|codex|computer-use|babbage|davinci|^chat-latest|chat-latest$|^sora)"
)
DEFAULT_LOOKBACK_DAYS = 180
_SNAPSHOT_SUFFIX = re.compile(r"-(\d{4}-\d{2}-\d{2}|\d{8})$")


def _get(url: str, headers: dict) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
        return json.load(r)


def fetch_openai() -> dict[str, dt.date]:
    key = load_env_value("OPENAI_API_KEY")
    data = _get("https://api.openai.com/v1/models", {"Authorization": f"Bearer {key}"})["data"]
    return {m["id"]: dt.date.fromtimestamp(m["created"]) for m in data}


def fetch_anthropic() -> dict[str, dt.date]:
    key = load_env_value("ANTHROPIC_API_KEY")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    out: dict[str, dt.date] = {}
    after = None
    while True:
        url = "https://api.anthropic.com/v1/models?limit=100" + (
            f"&after_id={after}" if after else ""
        )
        page = _get(url, headers)
        for m in page["data"]:
            out[m["id"]] = dt.date.fromisoformat(m["created_at"][:10])
        if not page.get("has_more"):
            return out
        after = page["last_id"]


def candidates(provider: str, served: dict[str, dt.date], show_all: bool) -> dict[str, dt.date]:
    """Served ids worth showing: drop non-text families and redundant dated snapshots."""
    if show_all:
        return served
    keep = {}
    for model_id, created in served.items():
        if provider == "openai" and (
            _OPENAI_NON_TEXT.search(model_id) or not model_id.startswith(("gpt-", "o"))
        ):
            continue
        alias = _SNAPSHOT_SUFFIX.sub("", model_id)
        if alias != model_id and (alias in served or alias in MODELS):
            continue
        keep[model_id] = created
    return keep


def main() -> int:
    ap = argparse.ArgumentParser(description="List provider models not yet in model_registry.py.")
    ap.add_argument(
        "--since",
        type=dt.date.fromisoformat,
        default=dt.date.today() - dt.timedelta(days=DEFAULT_LOOKBACK_DAYS),
        help=f"only show NEW models released on/after this date "
        f"(default: {DEFAULT_LOOKBACK_DAYS} days ago)",
    )
    ap.add_argument("--all", action="store_true", help="don't filter snapshots / non-text families")
    args = ap.parse_args()

    fetchers = {"openai": fetch_openai, "anthropic": fetch_anthropic}
    needs_pricing: set[str] = set()
    for provider, fetch in fetchers.items():
        try:
            served = fetch()
        except OSError as e:
            print(f"[{provider}] could not list models ({e}) — run `make check-keys`")
            continue
        registered = {slug for slug, m in MODELS.items() if m.get("provider") == provider}
        # A registered alias counts as served if the provider lists it or a dated snapshot of it.
        served_aliases = set(served) | {_SNAPSHOT_SUFFIX.sub("", s) for s in served}

        new = {
            mid: created
            for mid, created in candidates(provider, served, args.all).items()
            if mid not in MODELS and (args.all or created >= args.since)
        }
        unpriced = sorted(s for s in registered if s not in PRICE_PER_MILLION_USD)
        gone = sorted(s for s in registered if s not in served_aliases)

        print(f"=== {provider} — {len(served)} served, {len(registered)} registered ===")
        for mid, created in sorted(new.items(), key=lambda kv: kv[1], reverse=True):
            print(f"  NEW       {mid:<32} released {created}")
        for slug in unpriced:
            print(f"  UNPRICED  {slug}")
        for slug in gone:
            print(f"  GONE      {slug:<32} registered but no longer served")
        if not (new or unpriced or gone):
            print("  up to date")
        if new or unpriced:
            needs_pricing.add(provider)
        print()

    for provider in sorted(needs_pricing):
        print(f"Prices for {provider}: {PRICING_PAGES[provider]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
