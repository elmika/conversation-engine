#!/usr/bin/env python3
"""Head-to-head comparison of candidate models for `course-outline-proposal`.

Runs the REAL setup flow (framing Q&A → outline turn) against the running stack for
a fixed set of test profiles, once per candidate model — everything up to the final
turn is identical; only the outline turn's `model_slug` differs. This exercises the
actual prompt template, phase-switching, and rendering code, not a re-implementation
of it, so the comparison reflects what a real learner would see.

Makes real OpenAI calls (small but non-trivial cost — the whole point is comparing
two paid models on the same expensive-tier turn). NOT part of the pytest suite.

Prerequisites:
  - stack running:           make up
  - real OPENAI_API_KEY in:  .env
  - real ADMIN_TOKEN in:     .env (this script drives prompt/model overrides through
    the admin-only /admin/u/{user_id}/... routes — see docs/model-decisions.md /
    ConversationRequest's docstring for why the override isn't on the learner routes)
  - candidate models registered in app/domain/model_registry.py (validate_model_slug
    rejects anything not listed there)

Usage:
  python3 scripts/compare_outline_models.py [--base-url URL] [--models a,b]

Output: for each test profile, the two models' outline text + latency, printed
side by side for manual quality judgment (docs/roadmap.md "Evaluate GPT-5.6 Luna").
This script makes no pass/fail judgment — outline quality is a human call.

Results: every run is recorded in evals/results/outline_compare.jsonl (committed) via
scripts/model_compare_results.py — see its docstring for the record format and key
(profile answers + model + both prompts' bodies + user-profile-collection's pinned
model, which runs the framing turns). Re-running with an extra model or profile only
pays for the new cells; editing either prompt's text, or re-pinning
user-profile-collection, forces fresh runs. --refresh re-runs anyway and appends a
newer record (never overwrites); --no-record runs live without recording; --label tags
records with the test they belong to (e.g. "Test 8", matching docs/model-decisions.md).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_compare_results import ResultsLog, read_prompts  # noqa: E402
from session_test_utils import check_http_url, turn_models  # noqa: E402

TARGET = "course-outline-proposal"
# The outline prompt itself, plus the framing prompt that drives the 3 turns before it
# (setup_flow.py's FRAMING_TURNS) — see model_compare_results.py for how both feed the key.
SCENARIO_PROMPTS = [TARGET, "user-profile-collection"]


def _load_admin_token() -> str:
    """Read ADMIN_TOKEN from the environment, falling back to .env (no python-dotenv
    dependency — this script deliberately stays stdlib-only, see CLAUDE.md)."""
    if os.environ.get("ADMIN_TOKEN"):
        return os.environ["ADMIN_TOKEN"]
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ADMIN_TOKEN="):
                return line.split("=", 1)[1].strip()
    return ""


ADMIN_TOKEN = _load_admin_token()

DEFAULT_MODELS = ["gpt-5.4-pro", "gpt-5.6-luna"]

# Fixed test profiles, one canned answer per framing question (name, industry,
# motivation, session length) in the order prompts/user-profile-collection.md asks
# them. Deliberately varied industry/goal/technical-level so the comparison isn't
# tuned to one course shape.
PROFILES = [
    {
        "label": "backend-engineer-pandas",
        "answers": [
            "Alex",
            "I'm a backend engineer, mostly Python and Go services.",
            "I want to learn pandas well enough to do ad hoc fraud-data analysis without "
            "bugging the data team for every query.",
            "About 30 minutes per session.",
        ],
    },
    {
        "label": "marketing-manager-sql",
        "answers": [
            "Priya",
            "I run marketing campaigns at a mid-size retail company, not technical.",
            "I keep waiting on analysts for basic campaign reports — I want to write my own "
            "SQL queries against our data warehouse.",
            "Maybe 15-20 minutes, I'm busy.",
        ],
    },
    {
        "label": "product-manager-llm-features",
        "answers": [
            "Jordan",
            "Product manager at a SaaS startup, come from a design background.",
            "My team keeps shipping LLM-powered features and I want to actually understand "
            "how prompting, context windows, and evals work so I can review specs properly.",
            "An hour if I can get it, I like to go deep.",
        ],
    },
    # --- Round 2 (2026-08-07): wider topic spread — healthcare, small business, education,
    # creative/design, finance — deliberately outside the software-engineering cluster round 1
    # leaned on, per docs/architecture-decisions.md §5.
    {
        "label": "nurse-research-statistics",
        "answers": [
            "Maria",
            "I'm a registered nurse doing clinical research on the side.",
            "I want to understand basic statistics well enough to read and critique research "
            "papers, and eventually run simple analyses for a small study myself.",
            "20 minutes, between shifts.",
        ],
    },
    {
        "label": "bakery-owner-spreadsheets",
        "answers": [
            "Devon",
            "I own a small bakery, three employees, no technical background at all.",
            "I'm drowning in a messy spreadsheet for ingredient costs and orders — I want to "
            "learn Excel well enough to build something that actually tracks my margins.",
            "10-15 minutes, I barely have time to sit down.",
        ],
    },
    {
        "label": "teacher-python-classroom-tools",
        "answers": [
            "Sam",
            "I teach high school chemistry, I know how to use a computer but I've never coded.",
            "I want to learn enough Python to build small tools for my class — quiz generators, "
            "grade calculators, that kind of thing.",
            "About 30 minutes, usually in the evening.",
        ],
    },
    {
        "label": "designer-frontend-dev",
        "answers": [
            "Kai",
            "I'm a graphic designer, mostly Figma and Illustrator, no coding experience.",
            "I want to learn HTML, CSS, and a bit of JavaScript so I can actually build the "
            "landing pages I design instead of handing them off to a developer every time.",
            "45 minutes to an hour, I want to make real progress each time.",
        ],
    },
    {
        "label": "financial-analyst-vba-modeling",
        "answers": [
            "Priya",
            "I'm a financial analyst at an investment firm, very comfortable in Excel already.",
            "I want to learn VBA to automate the repetitive parts of my financial models instead "
            "of rebuilding the same formulas every quarter.",
            "About 30 minutes per session.",
        ],
    },
]


def _req(method: str, url: str, body: dict | None = None, timeout: int = 180) -> str:
    check_http_url(url)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if ADMIN_TOKEN:
        req.add_header("Authorization", f"Bearer {ADMIN_TOKEN}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode()


def _post_sse(url: str, body: dict, timeout: int = 180) -> dict:
    """POST an SSE turn; return the parsed `done` event payload."""
    raw = _req("POST", url, body, timeout=timeout)
    done: dict = {}
    deltas: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        try:
            d = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        if "delta" in d:
            deltas.append(d["delta"])
        elif "assistant_message" in d or "error" in d:
            done = d
    if not done.get("assistant_message") and deltas:
        done.setdefault("assistant_message", "".join(deltas))
    return done


def run_profile(base: str, db: str, profile: dict, model: str) -> dict:
    """Drive one setup conversation through all 4 framing turns; the 4th turn's
    model_slug is the candidate under test, which is exactly the turn that flips
    to the course-outline-proposal prompt (app/learning/setup_flow.py FRAMING_TURNS)."""
    uid = f"outline-eval-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cid: str | None = None
    try:
        init = _post_sse(
            f"{base}/admin/u/{uid}/conversations/init-stream",
            {"prompt_slug": "user-profile-collection"},
        )
        cid = init.get("conversation_id")

        answers = profile["answers"]
        for answer in answers[:-1]:
            _post_sse(
                f"{base}/admin/u/{uid}/conversations/{cid}/stream",
                {"messages": [{"role": "user", "content": answer}]},
            )

        t0 = time.monotonic()
        outline_turn = _post_sse(
            f"{base}/admin/u/{uid}/conversations/{cid}/stream",
            {"messages": [{"role": "user", "content": answers[-1]}], "model_slug": model},
        )
        wall_s = time.monotonic() - t0

        if "error" in outline_turn:
            return {"model": model, "error": outline_turn["error"]}
        timings = outline_turn.get("timings", {})
        return {
            "model": model,
            "outline": outline_turn.get("assistant_message", ""),
            "ttfb_ms": timings.get("ttfb_ms"),
            "total_ms": timings.get("total_ms"),
            "wall_s": round(wall_s, 1),
            "turn_models": turn_models(db, cid),
        }
    finally:
        if cid:
            try:
                _req("DELETE", f"{base}/u/{uid}/conversations/{cid}", timeout=15)
            except urllib.error.URLError:
                pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare candidate models on course-outline-proposal.")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument(
        "--models", default=",".join(DEFAULT_MODELS), help="comma-separated model_slugs"
    )
    ap.add_argument(
        "--profiles", default=None, help="comma-separated profile labels to run (default: all)"
    )
    ap.add_argument("--db", default="data/chat.db", help="path to the SQLite DB (host side)")
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="re-run even when a matching record exists, and append the newer record",
    )
    ap.add_argument(
        "--no-record", action="store_true", help="always run live and don't record the results"
    )
    ap.add_argument("--label", default=None, help='tag recorded runs, e.g. "Test 8"')
    args = ap.parse_args()
    if not ADMIN_TOKEN:
        print(
            "No ADMIN_TOKEN found (checked env and .env). This script drives the admin-only "
            "/admin/u/{user_id}/... routes and will fail with 401 without it."
        )
        return 2
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if args.profiles:
        wanted = {p.strip() for p in args.profiles.split(",") if p.strip()}
        profiles = [p for p in PROFILES if p["label"] in wanted]
    else:
        profiles = PROFILES

    try:
        health = _req("GET", f"{args.base_url}/healthz", timeout=5)
    except urllib.error.URLError as e:
        print(f"Stack not reachable at {args.base_url} ({e}). Start it with `make up`.")
        return 2
    print(f"stack healthy: {health.strip()}\ncomparing models: {models}\n")

    prompt_texts = read_prompts(SCENARIO_PROMPTS)
    log = ResultsLog("outline_compare")
    reused = 0
    live = 0

    for profile in profiles:
        print("=" * 100)
        print(f"PROFILE: {profile['label']}")
        print("=" * 100)
        for model in models:
            print(f"\n--- {model} ---")
            key = log.make_key(
                target=TARGET,
                profile_answers=profile["answers"],
                model=model,
                prompts=prompt_texts,
            )
            record = None if (args.no_record or args.refresh) else log.latest(key)
            if record is not None:
                result = record["result"]
                reused += 1
                print(
                    f"  (recorded {record['recorded_at']}"
                    + (f", {record['label']})" if record.get("label") else ")")
                )
            else:
                result = run_profile(args.base_url, args.db, profile, model)
                served_by = result.pop("turn_models", None)
                live += 1
                if "error" not in result and not args.no_record:
                    log.append(
                        key=key,
                        target=TARGET,
                        profile=profile["label"],
                        model=model,
                        prompts=prompt_texts,
                        result=result,
                        turn_models=served_by,
                        label=args.label,
                    )
            if "error" in result:
                print(f"  ERROR: {result['error']}")
                continue
            print(
                f"  ttfb={result['ttfb_ms']}ms total={result['total_ms']}ms"
                f" wall={result['wall_s']}s"
            )
            print(f"  {result['outline']}\n")

    print("=" * 100)
    print(f"results: {reused} from {log.path.relative_to(log.path.parents[2])}, {live} live run(s)")
    print("Done. This script makes no quality judgment — compare the outlines above by eye")
    print("(module relevance, tailoring to the stated goal/industry, scannability) before")
    print("deciding whether to switch course-outline-proposal.md's `model:` field.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
