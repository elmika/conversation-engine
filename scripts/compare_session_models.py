#!/usr/bin/env python3
"""Head-to-head comparison of candidate models for the chat-latency tier: the
session prompts a learner spends the most time in — `course-session-init`,
`course-session-core`, `course-session-closure` — plus `user-profile-collection`
(setup framing Q&A). See docs/model-decisions.md "Claude as a second provider".

Unlike compare_outline_models.py's single-turn comparison, these four prompts don't
share one shape (see --target below), so this script drives a purpose-built scenario
per target rather than one generic loop. In every scenario, only the turn(s) whose
prompt slug matches --target get an explicit model_slug override; every other turn
runs on its own currently-pinned model, so the comparison isolates the target prompt
(e.g. comparing course-session-core does NOT also vary the objective-complete guard's
model — that would confound the two).

Makes real LLM calls (small but non-trivial cost). NOT part of the pytest suite.

Prerequisites: same as compare_outline_models.py — `make up`, real OPENAI_API_KEY /
ANTHROPIC_API_KEY, real ADMIN_TOKEN in .env, candidate models registered in
app/domain/model_registry.py.

Usage:
  python3 scripts/compare_session_models.py --target course-session-init \
      --models claude-haiku-4-5,claude-sonnet-5-5
  python3 scripts/compare_session_models.py --target course-session-core --models claude-sonnet-5-5
  python3 scripts/compare_session_models.py --target user-profile-collection \
      --models claude-haiku-4-5

Caching: same mechanism and cache semantics as compare_outline_models.py (see its
docstring) via scripts/model_compare_cache.py, stored separately at
scripts/.cache/session_compare.json. --no-cache / --refresh behave the same way.
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_outline_models import PROFILES as _OUTLINE_PROFILES  # noqa: E402
from model_compare_cache import ComparisonCache  # noqa: E402
from session_test_utils import (  # noqa: E402
    ADMIN_TOKEN,
    age_conversation,
    cleanup_learner,
    post_sse,
    provision_learner,
    req,
    set_objective_met_db,
)

CACHE_PATH = Path(__file__).resolve().parent / ".cache" / "session_compare.json"
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

TARGETS = [
    "user-profile-collection",
    "course-session-init",
    "course-session-core",
    "course-session-closure",
]

# Trimmed subset of compare_outline_models.py's fixed profiles — reused so personas
# stay consistent across comparison scripts, trimmed to 3 to keep this tier's (4x
# more scenario shapes than the outline comparison) cost reasonable.
_SESSION_PROFILE_LABELS = {
    "backend-engineer-pandas",
    "marketing-manager-sql",
    "teacher-python-classroom-tools",
}
SESSION_PROFILES = [p for p in _OUTLINE_PROFILES if p["label"] in _SESSION_PROFILE_LABELS]

# Generic, topic-agnostic mid-lesson learner turns for the course-session-core scenario.
CORE_TURNS = [
    "Can you explain Module One in a bit more detail?",
    "Can you give me an example?",
    "I think I get it — what's next?",
]

SESSION_LENGTH_MINUTES = 15  # fixed, matches smoke_lesson_lifecycle.py's PROFILE_MINUTES
AGE_MINUTES = 20  # > length - buffer(3), forces the time-over guard deterministically


def _course_outline_for(profile: dict) -> str:
    title = profile["label"].replace("-", " ").title()
    goal = profile["answers"][2]
    return (
        f"# {title} Course\n\n1. Module One — Foundations\n"
        f"2. Module Two — Applied practice\n3. Module Three — Putting it together\n\n"
        f"Goal: {goal}\n"
    )


def _new_uid() -> str:
    return f"session-eval-{int(time.time())}-{uuid.uuid4().hex[:8]}"


def _turn_summary(result: dict) -> dict:
    return {
        "prompt_slug": result.get("prompt_slug"),
        "ttfb_ms": result.get("ttfb_ms"),
        "total_ms": result.get("total_ms"),
        "text": result.get("assistant_message", ""),
        "error": result.get("error"),
    }


def _run_user_profile_collection(
    base: str, sections: str, db: str, model: str, profile: dict
) -> dict:
    """Drive init + 3 framing turns (of 4) with model_slug=<candidate> — enough to
    exercise every user-profile-collection turn without also triggering the outline
    turn (the 4th answer), which is a different prompt on its own, already-decided
    model and irrelevant to this comparison."""
    uid = _new_uid()
    cid = None
    try:
        init = post_sse(
            f"{base}/admin/u/{uid}/conversations/init-stream",
            {"prompt_slug": "user-profile-collection", "model_slug": model},
        )
        cid = init.get("conversation_id")
        turns = [_turn_summary(init)]
        for answer in profile["answers"][:-1]:
            r = post_sse(
                f"{base}/admin/u/{uid}/conversations/{cid}/stream",
                {"messages": [{"role": "user", "content": answer}], "model_slug": model},
            )
            turns.append(_turn_summary(r))
        return {"turns": turns}
    finally:
        cleanup_learner(base, sections, uid, cid)


def _run_course_session_init(base: str, sections: str, db: str, model: str, profile: dict) -> dict:
    uid = _new_uid()
    cid = None
    try:
        provision_learner(
            sections, uid, profile, _course_outline_for(profile), SESSION_LENGTH_MINUTES
        )
        init = post_sse(
            f"{base}/admin/u/{uid}/conversations/init-stream",
            {"prompt_slug": "course-session-init", "model_slug": model},
        )
        cid = init.get("conversation_id")
        return {"turns": [_turn_summary(init)]}
    finally:
        cleanup_learner(base, sections, uid, cid)


def _run_course_session_core(base: str, sections: str, db: str, model: str, profile: dict) -> dict:
    uid = _new_uid()
    cid = None
    try:
        provision_learner(
            sections, uid, profile, _course_outline_for(profile), SESSION_LENGTH_MINUTES
        )
        init = post_sse(
            f"{base}/admin/u/{uid}/conversations/init-stream",
            {"prompt_slug": "course-session-init"},
        )
        cid = init.get("conversation_id")
        turns = []
        for content in CORE_TURNS:
            r = post_sse(
                f"{base}/admin/u/{uid}/conversations/{cid}/stream",
                {"messages": [{"role": "user", "content": content}], "model_slug": model},
            )
            turns.append(_turn_summary(r))
        return {"turns": turns}
    finally:
        cleanup_learner(base, sections, uid, cid)


def _run_course_session_closure(
    base: str, sections: str, db: str, model: str, profile: dict
) -> dict:
    uid = _new_uid()
    cid = None
    try:
        provision_learner(
            sections, uid, profile, _course_outline_for(profile), SESSION_LENGTH_MINUTES
        )
        init = post_sse(
            f"{base}/admin/u/{uid}/conversations/init-stream",
            {"prompt_slug": "course-session-init"},
        )
        cid = init.get("conversation_id")
        # one unvaried core turn, then force time-over and let the target model handle closure
        post_sse(
            f"{base}/admin/u/{uid}/conversations/{cid}/stream",
            {"messages": [{"role": "user", "content": CORE_TURNS[0]}]},
        )
        set_objective_met_db(db, cid, 0)
        age_conversation(db, cid, AGE_MINUTES)
        r = post_sse(
            f"{base}/admin/u/{uid}/conversations/{cid}/stream",
            {"messages": [{"role": "user", "content": "ok, what next?"}], "model_slug": model},
        )
        summary = _turn_summary(r)
        if summary["prompt_slug"] != "course-session-closure":
            print(
                f"  WARNING: expected course-session-closure, got {summary['prompt_slug']!r} "
                f"— time-over may not have forced closure; "
                f"result may not reflect the closure prompt."
            )
        return {"turns": [summary]}
    finally:
        cleanup_learner(base, sections, uid, cid)


SCENARIOS = {
    "user-profile-collection": _run_user_profile_collection,
    "course-session-init": _run_course_session_init,
    "course-session-core": _run_course_session_core,
    "course-session-closure": _run_course_session_closure,
}

# Prompt files whose text can change a given target's scenario output — used as part
# of the cache key so editing any of them busts stale cached results.
_SCENARIO_PROMPT_FILES = {
    "user-profile-collection": ["user-profile-collection.md"],
    "course-session-init": ["course-session-init.md"],
    "course-session-core": ["course-session-init.md", "course-session-core.md"],
    "course-session-closure": [
        "course-session-init.md",
        "course-session-core.md",
        "course-session-closure.md",
    ],
}


def _prompt_texts(target: str) -> dict[str, str]:
    return {name: (PROMPTS_DIR / name).read_text() for name in _SCENARIO_PROMPT_FILES[target]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare candidate models on the chat-latency tier.")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--db", default="data/chat.db", help="path to the SQLite DB (host side)")
    ap.add_argument("--sections", default="sections", help="path to the sections/ dir (host side)")
    ap.add_argument("--target", required=True, choices=TARGETS)
    ap.add_argument("--models", required=True, help="comma-separated model_slugs")
    ap.add_argument(
        "--profiles",
        default=None,
        help="comma-separated profile labels to run (default: the 3 built-in session profiles)",
    )
    ap.add_argument("--no-cache", action="store_true", help="ignore and don't update the cache")
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="call the live models even on a cache hit, and overwrite the cached entry",
    )
    args = ap.parse_args()
    if not ADMIN_TOKEN:
        print(
            "No ADMIN_TOKEN found (checked env and .env). This script drives admin-only routes "
            "and will fail with 401 without it."
        )
        return 2

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if args.profiles:
        wanted = {p.strip() for p in args.profiles.split(",") if p.strip()}
        profiles = [p for p in SESSION_PROFILES if p["label"] in wanted]
    else:
        profiles = SESSION_PROFILES

    try:
        health = req("GET", f"{args.base_url}/healthz", timeout=5)
    except OSError as e:
        print(f"Stack not reachable at {args.base_url} ({e}). Start it with `make up`.")
        return 2
    print(f"stack healthy: {health.strip()}\ntarget: {args.target}\ncomparing models: {models}\n")

    prompt_texts = _prompt_texts(args.target)
    scenario = SCENARIOS[args.target]
    cache = ComparisonCache(CACHE_PATH)
    cache_hits = 0
    cache_misses = 0

    for profile in profiles:
        print("=" * 100)
        print(f"PROFILE: {profile['label']}")
        print("=" * 100)
        for model in models:
            print(f"\n--- {model} ---")
            key = cache.make_key(
                target=args.target,
                profile_answers=profile["answers"],
                model=model,
                prompts=prompt_texts,
            )
            cached = None if args.no_cache else cache.get(key)
            if cached is not None and not args.refresh:
                result = cached
                cache_hits += 1
                print("  (cached)")
            else:
                result = scenario(args.base_url, args.sections, args.db, model, profile)
                cache_misses += 1
                has_error = any(t.get("error") for t in result["turns"])
                if not has_error and not args.no_cache:
                    cache.set(key, result)
                    cache.save()
            for i, turn in enumerate(result["turns"], start=1):
                if turn.get("error"):
                    print(f"  turn {i} ERROR: {turn['error']}")
                    continue
                print(
                    f"  turn {i} [{turn['prompt_slug']}] "
                    f"ttfb={turn['ttfb_ms']}ms total={turn['total_ms']}ms"
                )
                print(f"    {turn['text']}\n")

    print("=" * 100)
    print(f"cache: {cache_hits} hit(s), {cache_misses} live call(s)")
    print(
        "Done. No pass/fail judgment — compare latency and text quality above by eye "
        "before deciding whether to switch this prompt's `model:` field."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
