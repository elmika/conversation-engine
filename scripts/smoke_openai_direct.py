#!/usr/bin/env python3
"""Live smoke test against the OpenAI Responses API directly (not the app).

Calls the exact same SDK surface as `OpenAILLMAdapter.complete()`
(`app/infra/llm_openai.py`) -- `OpenAI(api_key=...)` then `.responses.create(...)`
-- and asserts the response shape `_extract_output_text` expects still holds:
`response.output` -> an item with `type == "message"` -> a content block with
`type == "output_text"`. This is the actual risk it's meant to catch: OpenAI
changing the Responses API payload shape out from under the app.

One non-streaming check is enough for v1; a streaming-shape check is lower
priority and skipped for now.

This bypasses Docker and the app entirely, so it needs:
  - `OPENAI_API_KEY` in your *local* shell env (not `.env`/Docker) -- e.g.
    `export OPENAI_API_KEY=sk-...` before running.
  - the `openai` package installed locally: `pip install "openai>=1.0"`
    (matches requirements.txt's pin; not installed in your host Python by
    default since everything else in this repo runs in Docker).

Makes one real, small OpenAI API call (small cost). Run by hand right before
each pilot/demo session -- not on a schedule, no CI wiring yet.

Usage:
  python3 scripts/smoke_openai_direct.py [--model MODEL]
"""

from __future__ import annotations

import argparse
import os
import sys

DEFAULT_MODEL = "gpt-4.1"  # matches app/settings.py's Settings.default_model


class Smoke:
    def __init__(self) -> None:
        self.results: list[tuple[bool, str]] = []

    def check(self, ok: bool, msg: str) -> None:
        self.results.append((ok, msg))
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")


def _extract_output_text(response: object) -> str:
    """Same walk as app/infra/llm_openai.py::_extract_output_text -- kept as a
    separate copy on purpose: this script exists to catch drift in the shape
    that function assumes, so it must not import the function under test."""
    output = getattr(response, "output", None) or []
    for item in output:
        if getattr(item, "type", None) != "message":
            continue
        content = getattr(item, "content", None) or []
        for block in content:
            if getattr(block, "type", None) == "output_text":
                return getattr(block, "text", None) or ""
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Live smoke test of the OpenAI Responses API shape.")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set in your shell env. Export it and re-run.")
        return 2

    try:
        from openai import OpenAI
    except ImportError:
        print("The `openai` package is not installed locally. Run: pip install \"openai>=1.0\"")
        return 2

    client = OpenAI(api_key=api_key)
    smoke = Smoke()

    print(f"model: {args.model}\n")
    try:
        response = client.responses.create(
            model=args.model,
            instructions="You are a concise assistant. Reply with exactly one short sentence.",
            input=[{"role": "user", "content": [{"type": "input_text", "text": "Say hello."}]}],
            max_output_tokens=64,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001 - report any failure as a smoke failure, not a crash
        smoke.check(False, f"responses.create() succeeded (raised {exc.__class__.__name__}: {exc})")
        print(f"\n{sum(1 for r, _ in smoke.results if r)}/{len(smoke.results)} checks passed")
        return 1

    smoke.check(True, "responses.create() succeeded")

    output = getattr(response, "output", None) or []
    smoke.check(bool(output), "response.output is non-empty")

    message_items = [item for item in output if getattr(item, "type", None) == "message"]
    smoke.check(bool(message_items), "response.output contains an item with type == 'message'")

    text = _extract_output_text(response)
    smoke.check(bool(text.strip()), f"extracted non-empty output_text (got {text!r})")

    ok = all(r for r, _ in smoke.results)
    print(f"\n{sum(1 for r, _ in smoke.results if r)}/{len(smoke.results)} checks passed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
