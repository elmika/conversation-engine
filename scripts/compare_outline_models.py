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
  - candidate models registered in app/domain/model_registry.py (validate_model_slug
    rejects anything not listed there)

Usage:
  python3 scripts/compare_outline_models.py [--base-url URL] [--models a,b]

Output: for each test profile, the two models' outline text + latency, printed
side by side for manual quality judgment (docs/roadmap.md "Evaluate GPT-5.6 Luna").
This script makes no pass/fail judgment — outline quality is a human call.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

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
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
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


def run_profile(base: str, profile: dict, model: str) -> dict:
    """Drive one setup conversation through all 4 framing turns; the 4th turn's
    model_slug is the candidate under test, which is exactly the turn that flips
    to the course-outline-proposal prompt (app/learning/setup_flow.py FRAMING_TURNS)."""
    uid = f"outline-eval-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cid: str | None = None
    try:
        init = _post_sse(
            f"{base}/u/{uid}/conversations/init-stream",
            {"prompt_slug": "user-profile-collection"},
        )
        cid = init.get("conversation_id")

        answers = profile["answers"]
        for answer in answers[:-1]:
            _post_sse(f"{base}/u/{uid}/conversations/{cid}/stream", {"messages": [{"role": "user", "content": answer}]})

        t0 = time.monotonic()
        outline_turn = _post_sse(
            f"{base}/u/{uid}/conversations/{cid}/stream",
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
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS), help="comma-separated model_slugs")
    ap.add_argument(
        "--profiles", default=None, help="comma-separated profile labels to run (default: all)"
    )
    args = ap.parse_args()
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

    for profile in profiles:
        print("=" * 100)
        print(f"PROFILE: {profile['label']}")
        print("=" * 100)
        for model in models:
            print(f"\n--- {model} ---")
            result = run_profile(args.base_url, profile, model)
            if "error" in result:
                print(f"  ERROR: {result['error']}")
                continue
            print(f"  ttfb={result['ttfb_ms']}ms total={result['total_ms']}ms wall={result['wall_s']}s")
            print(f"  {result['outline']}\n")

    print("=" * 100)
    print("Done. This script makes no quality judgment — compare the outlines above by eye")
    print("(module relevance, tailoring to the stated goal/industry, scannability) before")
    print("deciding whether to switch course-outline-proposal.md's `model:` field.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
