"""File-based SlotResolver adapter — Layer 1b default.

Reads sections/<tag>/default.md from a base directory. Shipped as part of
Layer 1b so the prompt templating engine works standalone without any upper
layer bound. Layer 2 swaps this out with a DB-backed adapter when active.
"""

from pathlib import Path
from typing import Optional


class FileSlotResolver:
    """Resolves slot tags by reading sections/<tag>/default.md."""

    def __init__(self, sections_dir: str) -> None:
        self._base = Path(sections_dir)

    def resolve(self, tag: str) -> Optional[str]:
        """Return content of sections/<tag>/default.md, or None if the file doesn't exist."""
        path = self._base / tag / "default.md"
        return path.read_text(encoding="utf-8") if path.exists() else None
