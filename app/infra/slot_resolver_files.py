"""File-based SlotResolver adapter — Layer 1b default.

Reads sections/<tag>/<user_id>.md from a base directory. Shipped as part of
Layer 1b so the prompt templating engine works standalone without any upper
layer bound. Layer 2 swaps this out with a DB-backed adapter when active.
"""

from pathlib import Path
from typing import Optional


class FileSlotResolver:
    """Resolves slot tags by reading sections/<tag>/<user_id>.md."""

    def __init__(self, sections_dir: str, user_id: str = "default") -> None:
        self._base = Path(sections_dir)
        self._user_id = user_id

    def resolve(self, tag: str) -> Optional[str]:
        """Return content of sections/<tag>/<user_id>.md, or None if the file doesn't exist."""
        path = self._base / tag / f"{self._user_id}.md"
        return path.read_text(encoding="utf-8") if path.exists() else None
