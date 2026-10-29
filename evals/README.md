# Model comparison results

Raw outputs from the head-to-head model comparisons behind `docs/model-decisions.md`. Each
test there ("Test 6", "Test 7", …) is a write-up; the records here are what it was judged on.

| File | Written by | What's compared |
|---|---|---|
| `results/outline_compare.jsonl` | `scripts/compare_outline_models.py` | `course-outline-proposal` — the course outline generated at the end of setup |
| `results/session_compare.jsonl` | `scripts/compare_session_models.py` | `course-session-init/core/closure` (the lesson) and `user-profile-collection` (setup Q&A) |

Every run drives the real app end to end with a fixed, fictional learner profile; only the
turns of the prompt under test (`target`) use the candidate `model`, everything else runs on
its normal model. Nothing here is judged automatically — quality calls are made by reading
the outputs side by side.

## Record format

One JSON object per line, append-only — a re-run adds a newer record, it never replaces one.

| Field | Meaning |
|---|---|
| `label` | Which test this belongs to, e.g. `"Test 7"` (matches `docs/model-decisions.md`) |
| `recorded_at` | When the run happened (UTC). Records migrated from the old cache only have a date |
| `git` | Commit the run was made from, and whether the working tree had uncommitted changes |
| `target`, `profile`, `model` | Prompt under test, learner profile, candidate model |
| `prompts` | Fingerprint of each prompt involved (its text minus the `model:` line) — the prompts themselves aren't stored |
| `context_models` | Models pinned on the scenario's *other* prompts at the time |
| `turn_models` | The model that actually served each turn, read from the app's `runs` table (`null` for migrated records) |
| `result` | The outputs: `turns` (text, `ttfb_ms` = time to first token, `total_ms`) for session runs; `outline` + timings for outline runs |
| `key` | Lookup key — runs with the same key are interchangeable, so the scripts reuse the latest one instead of paying again |

Quick look at one test:

```bash
jq -c 'select(.label == "Test 7") | {target, profile, model, ttfb: [.result.turns[].ttfb_ms]}' \
  evals/results/session_compare.jsonl
```
