#!/usr/bin/env python3
"""Live smoke test for the course-session lifecycle (intro -> core -> closure).

Exercises the RUNNING stack end-to-end against the real API. This makes real
OpenAI calls (it has a small cost) and is therefore NOT part of the pytest suite,
which never touches the network. Run it by hand after changes to the lesson flow.

Prerequisites:
  - stack running:           make up
  - real OPENAI_API_KEY in:  .env

Usage:
  python3 scripts/smoke_lesson_lifecycle.py [--base-url URL] [--db PATH]

What it verifies (each step inspects the SSE `meta.prompt_slug` and the DB):
  1. init session         -> course-session-init; session_length seeded from profile (15)
  2. core turn            -> course-session-core; length unchanged
  3. "do 30 today"        -> length captured == 30                    (3b extraction)
  4. time over (poked)    -> course-session-closure                  (3c orchestration)
  5. "make it 60" + next  -> length == 60, then resumes course-session-core
  6. objective_met (poked)-> course-session-closure even within time (3d orchestration)

It provisions an isolated smoke user (profile/course/progress section files) and
deletes the user + conversation on exit, so it never touches real learner data.

Note: steps 1/3/5 read and step 4 pokes `conversations.created_at` directly in the
SQLite DB — a deliberate test shortcut to force "time over" without waiting real
minutes. No application code depends on this.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PROFILE_MINUTES = 15  # must match the "## Session length" written below


def _req(method: str, url: str, body: dict | None = None, timeout: int = 90) -> str:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode()


def _post_sse(url: str, body: dict) -> tuple[str | None, str | None, str]:
    """POST an SSE turn; return (meta.prompt_slug, meta.conversation_id, assistant text)."""
    raw = _req("POST", url, body)
    prompt_slug, conv_id, deltas, final_text = None, None, [], ""
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        try:
            d = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        if "prompt_slug" in d and prompt_slug is None:
            prompt_slug = d["prompt_slug"]
            conv_id = d.get("conversation_id")
        elif "delta" in d:
            deltas.append(d["delta"])
        elif "assistant_message" in d:
            final_text = d["assistant_message"]
    return prompt_slug, conv_id, ("".join(deltas) or final_text)


class Smoke:
    def __init__(self, base_url: str, db_path: str, sections_dir: str) -> None:
        self.base = base_url.rstrip("/")
        self.db_path = db_path
        self.sections = Path(sections_dir)
        self.uid = f"smoke-{int(time.time())}-{uuid.uuid4()}"
        self.cid: str | None = None
        self.results: list[tuple[bool, str]] = []

    # --- helpers -----------------------------------------------------------
    def check(self, ok: bool, msg: str) -> None:
        self.results.append((ok, msg))
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    def session_length(self) -> int | None:
        con = self._db()
        try:
            row = con.execute(
                "SELECT session_length_minutes FROM conversations WHERE id = ?", (self.cid,)
            ).fetchone()
            return row[0] if row else None
        finally:
            con.close()

    def age_conversation(self, minutes: int) -> None:
        con = self._db()
        try:
            con.execute(
                "UPDATE conversations SET created_at = datetime(created_at, ?) WHERE id = ?",
                (f"-{minutes} minutes", self.cid),
            )
            con.commit()
        finally:
            con.close()

    def set_objective_met_db(self, value: int) -> None:
        con = self._db()
        try:
            con.execute(
                "UPDATE conversations SET objective_met = ? WHERE id = ?", (value, self.cid)
            )
            con.commit()
        finally:
            con.close()

    # --- lifecycle ---------------------------------------------------------
    def setup_user(self) -> None:
        (self.sections / "user").mkdir(parents=True, exist_ok=True)
        (self.sections / "course").mkdir(parents=True, exist_ok=True)
        (self.sections / "progress").mkdir(parents=True, exist_ok=True)
        (self.sections / "user" / f"{self.uid}.md").write_text(
            "## Name\nSmoke\n\n## Work\nQA engineer running an automated smoke test.\n\n"
            "## Technical background\nHands-on; comfortable with Python and APIs.\n\n"
            "## Goal\nVerify the course session lifecycle works end to end.\n\n"
            f"## Session length\n{PROFILE_MINUTES} minutes\n\n## Other context\nNot yet provided.\n"
        )
        (self.sections / "course" / f"{self.uid}.md").write_text(
            "# Smoke Test Course\n\n1. Module One — Basics\n2. Module Two — Intermediate\n"
            "3. Module Three — Advanced\n"
        )
        (self.sections / "progress" / f"{self.uid}.md").write_text(
            "## What the student knows\nNo learning sessions completed yet.\n\n"
            "## Progress - Current state\n- Begin Module 1 this session.\n"
        )

    def run(self) -> bool:
        status = json.loads(_req("GET", f"{self.base}/u/{self.uid}/status"))
        self.check(status.get("has_profile") is True, "status: has_profile is true")

        # 1. init -> intro prompt, length seeded from profile
        slug, self.cid, _ = _post_sse(
            f"{self.base}/u/{self.uid}/conversations/init-stream",
            {"prompt_slug": "course-session-init"},
        )
        self.check(slug == "course-session-init", f"init uses course-session-init (got {slug})")
        self.check(self.cid is not None, "init created an addressable conversation")
        self.check(
            self.session_length() == PROFILE_MINUTES,
            f"session_length seeded from profile == {PROFILE_MINUTES} (got {self.session_length()})",
        )

        # 2. core turn (no duration mention) -> core, length unchanged
        slug, _ = self._turn("Can you explain Module One in a bit more detail?")
        self.check(slug == "course-session-core", f"core turn uses course-session-core (got {slug})")
        self.check(self.session_length() == PROFILE_MINUTES, "length unchanged after non-duration turn")

        # 3. in-chat adjustment captured (3b)
        self._turn("Actually, can we do 30 minutes today instead?")
        time.sleep(1)
        self.check(self.session_length() == 30, f"duration change captured == 30 (got {self.session_length()})")

        # 4. force time over -> closure (3c)
        self.age_conversation(40)  # 40 > 30 - buffer(3) => time over
        slug, _ = self._turn("ok, what next?")
        self.check(slug == "course-session-closure", f"time-over turn uses course-session-closure (got {slug})")

        # 5. extend during wind-down, then resume core (isolate the TIME dimension)
        self._turn("Actually I have more time — let's make it 60 minutes today.")
        time.sleep(1)
        self.check(self.session_length() == 60, f"extension captured == 60 (got {self.session_length()})")
        # Clear any objective latch the real guard may have set, so this checks the
        # time dimension alone (60 min length vs ~40 min elapsed → back to core).
        self.set_objective_met_db(0)
        slug, _ = self._turn("great, let's keep going then")
        self.check(slug == "course-session-core", f"next turn resumes course-session-core (got {slug})")

        # 6. objective met (poked) -> closure even with time remaining (3d)
        self.set_objective_met_db(1)
        slug, _ = self._turn("makes sense — anything else?")
        self.check(slug == "course-session-closure", f"objective-met turn uses course-session-closure (got {slug})")

        return all(ok for ok, _ in self.results)

    def _turn(self, content: str) -> tuple[str | None, str]:
        slug, _cid, text = _post_sse(
            f"{self.base}/u/{self.uid}/conversations/{self.cid}/stream",
            {"messages": [{"role": "user", "content": content}]},
        )
        return slug, text

    def cleanup(self) -> None:
        if self.cid:
            try:
                _req("DELETE", f"{self.base}/u/{self.uid}/conversations/{self.cid}", timeout=15)
            except urllib.error.URLError:
                pass
        for tag in ("user", "course", "progress"):
            (self.sections / tag / f"{self.uid}.md").unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Live course-session lifecycle smoke test.")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--db", default="data/chat.db", help="path to the SQLite DB (host side)")
    ap.add_argument("--sections", default="sections", help="path to the sections/ dir (host side)")
    args = ap.parse_args()

    try:
        health = _req("GET", f"{args.base_url}/healthz", timeout=5)
    except urllib.error.URLError as e:
        print(f"Stack not reachable at {args.base_url} ({e}). Start it with `make up`.")
        return 2
    print(f"stack healthy: {health.strip()}")

    smoke = Smoke(args.base_url, args.db, args.sections)
    print(f"smoke user: {smoke.uid}\n")
    try:
        smoke.setup_user()
        ok = smoke.run()
    finally:
        smoke.cleanup()

    passed = sum(1 for r, _ in smoke.results if r)
    print(f"\n{passed}/{len(smoke.results)} checks passed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
