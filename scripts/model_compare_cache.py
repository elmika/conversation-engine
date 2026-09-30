"""Disk cache for model-comparison scripts (compare_outline_models.py and future
per-tier siblings — see docs/model-decisions.md "Claude as a second provider").

Every comparison run makes real, paid LLM calls. Re-running a script to add one more
model or profile re-pays for every model/profile combination already tested, not just
the new ones. This cache keys each result by everything that can change its content —
model slug, profile inputs, and the exact prompt template text used — so an unrelated
addition (a new model, a new profile) only spends money on the new cells, and an actual
prompt edit correctly busts the cache instead of silently serving a stale response.

Stdlib-only, matching the comparison scripts themselves (see their own docstrings on
why: no python-dotenv/requests dependency for a script that only runs by hand).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ComparisonCache:
    """A flat {key: result} JSON file on disk, keyed by a content hash.

    Not safe for concurrent writers — these scripts run as a single foreground
    process, so that's never a real constraint.
    """

    def __init__(self, path: Path):
        self.path = path
        self._data: dict[str, Any] = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text())

    @staticmethod
    def make_key(**parts: Any) -> str:
        """Hash every part that affects the result. Callers should pass the raw
        content that matters (prompt file text, profile answers, model slug) rather
        than a proxy like a filename or a profile label, so an edit to either
        invalidates old entries instead of silently reusing them."""
        canonical = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def get(self, key: str) -> dict | None:
        return self._data.get(key)

    def set(self, key: str, value: dict) -> None:
        self._data[key] = value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True))
