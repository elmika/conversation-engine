"""Per-conversation session summary snapshots — Layer 2.

build_session_summary() reads the learner's *current* course and progress files, which every
later session (and a new setup) overwrites. Building it on demand made every past session show
today's state. So the summary is built once, when the session ends, and stored next to the
other learner files:

    sections/summaries/<user_id>/<conversation_id>.json

A conversation with no snapshot (a setup conversation, or one ended before snapshots existed)
has no summary: showing the current state for it would be wrong, not just stale.
"""

import json
import re
from pathlib import Path
from typing import Optional

# Ids reach here from the URL. Refuse anything that could leave the summaries directory.
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]+")


def _snapshot_path(sections_dir: str, user_id: str, conversation_id: str) -> Path:
    if not (_SAFE_ID.fullmatch(user_id) and _SAFE_ID.fullmatch(conversation_id)):
        raise ValueError("unsafe id for a summary snapshot path")
    return Path(sections_dir) / "summaries" / user_id / f"{conversation_id}.json"


def save_summary_snapshot(
    sections_dir: str, user_id: str, conversation_id: str, summary: dict
) -> None:
    path = _snapshot_path(sections_dir, user_id, conversation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")


def load_summary_snapshot(sections_dir: str, user_id: str, conversation_id: str) -> Optional[dict]:
    path = _snapshot_path(sections_dir, user_id, conversation_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
