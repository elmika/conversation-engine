"""Shared helpers for scripts that drive a real learning session against the running
stack — currently used by compare_session_models.py. Factored out rather than
duplicated a third time; see that script's docstring for why.

Deliberately stdlib-only, matching every other hand-run script in scripts/ (see their
docstrings: no python-dotenv/requests dependency for a script that only runs by hand).
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def load_admin_token() -> str:
    """Read ADMIN_TOKEN from the environment, falling back to .env."""
    if os.environ.get("ADMIN_TOKEN"):
        return os.environ["ADMIN_TOKEN"]
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ADMIN_TOKEN="):
                return line.split("=", 1)[1].strip()
    return ""


ADMIN_TOKEN = load_admin_token()


def check_http_url(url: str) -> None:
    """Refuse anything but plain HTTP(S) before a request is sent.

    --base-url comes from the command line and requests carry the admin token, so a file://,
    ftp:// or typo'd scheme must fail loudly rather than be opened by urllib.
    """
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise ValueError(f"Refusing non-HTTP(S) URL: {url!r}")


def req(method: str, url: str, body: dict | None = None, timeout: int = 180) -> str:
    check_http_url(url)
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if ADMIN_TOKEN:
        request.add_header("Authorization", f"Bearer {ADMIN_TOKEN}")
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return resp.read().decode()


def post_sse(url: str, body: dict, timeout: int = 180) -> dict:
    """POST an SSE turn; return the merged meta + done payload: prompt_slug,
    conversation_id, assistant_message, ttfb_ms, total_ms, and error (if any)."""
    raw = req("POST", url, body, timeout=timeout)
    result: dict = {}
    deltas: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        try:
            d = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        if "prompt_slug" in d:
            result["prompt_slug"] = d["prompt_slug"]
            result["conversation_id"] = d.get("conversation_id")
        elif "delta" in d:
            deltas.append(d["delta"])
        elif "assistant_message" in d or "error" in d:
            result["assistant_message"] = d.get("assistant_message", "")
            if "error" in d:
                result["error"] = d["error"]
            timings = d.get("timings", {})
            result["ttfb_ms"] = timings.get("ttfb_ms")
            result["total_ms"] = timings.get("total_ms")
    if not result.get("assistant_message") and deltas:
        result["assistant_message"] = "".join(deltas)
    return result


def provision_learner(
    sections_dir: str, uid: str, profile: dict, course_outline: str, session_length_minutes: int
) -> None:
    """Write the profile/course/progress section files a completed setup would have
    produced — no live setup-flow LLM calls needed. `profile` is one of
    compare_outline_models.PROFILES's entries (label + answers: name, work, goal,
    session length). `session_length_minutes` is written as a clean number rather
    than the profile's own free-text answer, so callers that force time-over via
    age_conversation() get a deterministic threshold regardless of persona."""
    sections = Path(sections_dir)
    for tag in ("user", "course", "progress"):
        (sections / tag).mkdir(parents=True, exist_ok=True)
    name, work, goal, _session_length_text = profile["answers"]
    (sections / "user" / f"{uid}.md").write_text(
        f"## Name\n{name}\n\n## Work\n{work}\n\n"
        f"## Technical background\nSee work description.\n\n## Goal\n{goal}\n\n"
        f"## Session length\n{session_length_minutes} minutes\n\n"
        f"## Other context\nNot yet provided.\n"
    )
    (sections / "course" / f"{uid}.md").write_text(course_outline)
    (sections / "progress" / f"{uid}.md").write_text(
        "## What the student knows\nNo learning sessions completed yet.\n\n"
        "## Progress - Current state\n- Begin Module 1 this session.\n"
    )


def age_conversation(db_path: str, cid: str, minutes: int) -> None:
    """Rewind `conversations.created_at` so the time-over guard fires without
    waiting real minutes — same shortcut smoke_lesson_lifecycle.py uses."""
    con = sqlite3.connect(db_path, timeout=10)
    try:
        con.execute(
            "UPDATE conversations SET created_at = datetime(created_at, ?) WHERE id = ?",
            (f"-{minutes} minutes", cid),
        )
        con.commit()
    finally:
        con.close()


def set_objective_met_db(db_path: str, cid: str, value: int) -> None:
    con = sqlite3.connect(db_path, timeout=10)
    try:
        con.execute("UPDATE conversations SET objective_met = ? WHERE id = ?", (value, cid))
        con.commit()
    finally:
        con.close()


def turn_models(db_path: str, cid: str | None) -> list[dict]:
    """[{prompt_slug, model}] per assistant turn, from the `runs` table — the SSE stream
    deliberately doesn't expose the model, so this is how a comparison records which
    model actually served each turn. Read it before cleanup_learner() deletes the rows."""
    if not cid:
        return []
    con = sqlite3.connect(db_path, timeout=10)
    try:
        rows = con.execute(
            "SELECT prompt_slug, model FROM runs WHERE conversation_id = ? ORDER BY id", (cid,)
        ).fetchall()
    finally:
        con.close()
    return [{"prompt_slug": slug, "model": model} for slug, model in rows]


def cleanup_learner(base_url: str, sections_dir: str, uid: str, cid: str | None) -> None:
    if cid:
        try:
            req("DELETE", f"{base_url}/u/{uid}/conversations/{cid}", timeout=15)
        except urllib.error.URLError:
            pass
    sections = Path(sections_dir)
    for tag in ("user", "course", "progress"):
        (sections / tag / f"{uid}.md").unlink(missing_ok=True)
