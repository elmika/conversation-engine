"""Append-only results log for the model-comparison scripts (compare_outline_models.py,
compare_session_models.py, and future per-tier siblings).

Every comparison run makes real, paid LLM calls, and its outputs are the evidence behind
the decisions in docs/model-decisions.md — so results are *recorded*, not cached:
evals/results/<name>.jsonl is committed to git, one JSON record per (profile, model) run,
never overwritten. A re-run with --refresh appends a newer record; lookups return the
latest record for a key, so older ones stay as history (e.g. "did this model drift since
Test 6?").

The lookup key holds exactly what can change a run's output:
  - the profile inputs and the candidate model,
  - each involved prompt file's *body* — its `model:` frontmatter line is excluded,
    since the target prompt's pin is overridden by the candidate anyway,
  - the pinned model of every *non-target* prompt in the scenario ("context models"):
    those turns run on their pins, so switching one changes what the target sees.
So switching the target prompt's own pin reuses earlier results, while editing any
prompt's text or switching a context prompt's model correctly forces fresh runs.

Records store prompt fingerprints, not prompt text — prompts stay out of the log.

Stdlib-only, matching the comparison scripts themselves (see their own docstrings on
why: no python-dotenv/requests dependency for a script that only runs by hand).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "evals" / "results"
PROMPTS_DIR = ROOT / "prompts"

_MODEL_LINE = re.compile(r"^model:.*\n?", re.MULTILINE)


def _frontmatter_split(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[: end + 4], text[end + 4 :]
    return "", text


def pinned_model(prompt_text: str) -> str | None:
    """The `model:` value from a prompt file's frontmatter, if any."""
    front, _ = _frontmatter_split(prompt_text)
    m = re.search(r"^model:\s*(\S+)", front, re.MULTILINE)
    return m.group(1) if m else None


def prompt_fingerprint(prompt_text: str) -> str:
    """Hash of a prompt file with its `model:` frontmatter line removed."""
    front, body = _frontmatter_split(prompt_text)
    return hashlib.sha256((_MODEL_LINE.sub("", front) + body).encode()).hexdigest()[:16]


def read_prompts(names: list[str]) -> dict[str, str]:
    """{slug: file text} for prompts/<slug>.md."""
    return {name: (PROMPTS_DIR / f"{name}.md").read_text() for name in names}


def git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=ROOT, check=False
        ).stdout.strip()

    return {
        "commit": run("rev-parse", "--short", "HEAD") or None,
        "dirty": bool(run("status", "--porcelain")),
    }


class ResultsLog:
    """evals/results/<name>.jsonl — append-only, latest record per key wins on lookup.

    Not safe for concurrent writers — these scripts run as a single foreground
    process, so that's never a real constraint.
    """

    def __init__(self, name: str):
        self.path = RESULTS_DIR / f"{name}.jsonl"
        self._latest: dict[str, dict] = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    record = json.loads(line)
                    self._latest[record["key"]] = record

    @staticmethod
    def make_key(
        *, target: str, profile_answers: list[str], model: str, prompts: dict[str, str]
    ) -> str:
        """Key a run by everything that can change its output (see module docstring).
        `prompts` is {slug: file text} for every prompt in the scenario, target included."""
        parts = {
            "target": target,
            "profile_answers": profile_answers,
            "model": model,
            "prompts": {slug: prompt_fingerprint(text) for slug, text in prompts.items()},
            "context_models": {
                slug: pinned_model(text) for slug, text in prompts.items() if slug != target
            },
        }
        canonical = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def latest(self, key: str) -> dict | None:
        return self._latest.get(key)

    def append(
        self,
        *,
        key: str,
        target: str,
        profile: str,
        model: str,
        prompts: dict[str, str],
        result: dict,
        turn_models: list[dict] | None = None,
        label: str | None = None,
    ) -> dict:
        """Record one run, written to disk immediately so an interrupted comparison
        keeps everything it already paid for."""
        record = {
            "key": key,
            "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "label": label,
            "git": git_state(),
            "target": target,
            "profile": profile,
            "model": model,
            "prompts": {slug: prompt_fingerprint(text) for slug, text in prompts.items()},
            "context_models": {
                slug: pinned_model(text) for slug, text in prompts.items() if slug != target
            },
            "turn_models": turn_models,
            "result": result,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        self._latest[key] = record
        return record
