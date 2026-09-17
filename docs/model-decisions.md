# Model Decisions

Which OpenAI model each task uses, why, and the test history behind each choice.
Complements `docs/prompts.md` "Model presets" (the mechanism — `config/model_presets/`,
`scripts/apply_model_preset.py`) and `docs/roadmap.md` (open/in-progress items link back
here once a comparison actually runs). This file is the durable record of *what we tried
and why we landed where we did* — update it whenever a model comparison runs, whether or
not it results in a switch. A rejected candidate is exactly as worth recording as an
adopted one, so nobody re-runs the same comparison cold next quarter.

---

## Current configuration

Reference point: `config/model_presets/baseline-2026-09.json` + `course-outline-sol.json`
(see `docs/prompts.md`). Pricing: `app/domain/pricing.py`, refreshed 2026-09-17.

| Task (prompt slug) | Model | Why this tier | Last reviewed |
|---|---|---|---|
| `course-session-init` | `gpt-4.1` | Chat turn, latency-critical (learner is waiting live) | 2026-09-17 (prompt rewritten; model unchanged, not re-tested) |
| `course-session-core` | `gpt-4.1` | Chat turn, latency-critical | 2026-09-17 (prompt rewritten; model unchanged, not re-tested) |
| `course-session-closure` | `gpt-4.1` | Chat turn, latency-critical | 2026-09-17 (prompt rewritten; model unchanged, not re-tested) |
| `user-profile-collection` | `gpt-4.1` | Plain framing Q&A, no creative work — split off the outline turn specifically so this could run on a cheap/fast tier (roadmap item 1, 2026-08-04) | 2026-08-04 |
| `user-profile-extraction` | `gpt-5.4-mini` | Structured extraction from a short transcript | not re-tested since introduced |
| `course-outline-extraction` | `gpt-5.4-mini` | Structured extraction from a short transcript | not re-tested since introduced |
| `course-outline-proposal` | **`gpt-5.6-sol`** | The one generation worth paying for — one-shot, high-stakes, low volume (once per learner) | **2026-09-17** — see [Test 3](#test-3-2026-09-17--course-outline-proposal-gpt-56-sol-vs-gpt-6-astra) |
| `lesson-objective-complete` | `gpt-5.4-nano` | Single-token YES/NO guard, cheap+fast is the whole requirement | not re-tested since introduced |
| `session-length-extraction` | `gpt-5.4-nano` | Single-token/number extraction guard | not re-tested since introduced |
| `closure-continue-extraction` | `gpt-5.4-nano` | Single-token YES/NO guard (new 2026-09-17) | 2026-09-17 |
| `framing-answer-check` | `gpt-5.4-nano` | Single-token YES/NO guard (new 2026-09-17) | 2026-09-17 |
| `wrap_up_model` (progress synthesis, `sections/progress/progress-wrap-up.md`) | `gpt-5.6-luna` | The other generation worth paying for — **but not re-tested against sol; see rationale below** | 2026-08-07 |
| `default_model` (fallback) | `gpt-4.1` | — | — |

---

## `wrap_up_model` — why it's still on luna, not sol (2026-09-17)

`course-outline-proposal` and `wrap_up_model` were switched together from `gpt-5.4-pro` to
`gpt-5.6-luna` on 2026-08-07 (same evaluation, [architecture-decisions.md §5](architecture-decisions.md)) —
both were "the pro-tier calls worth paying for." That symmetry doesn't automatically carry
over to the luna → sol question:

**Volume is not symmetric.** `course-outline-proposal` runs exactly once per learner, on a
short, fixed-shape input (a 4-answer framing transcript, ~480 tokens observed). `wrap_up_model`
runs once per *lesson session* — every module, potentially every partial session within a
module now that same-module resume exists (2026-09-17) — against a growing progress doc
(354 words after just one session, only grows) plus the full session transcript (scales with
session length, up to the ~60-minute end of the stated range). Rough estimate: 3-6x the input
tokens per call even on a short session, before counting call frequency at all — Mika's estimate
of "5-7x more often, 5-10x longer input" puts aggregate token volume at roughly 25-70x the
outline's. The same per-token price jump that costs fractions of a cent on the outline would
cost real, recurring money on wrap-up at that volume.

**Task shape is not symmetric either.** The outline is one-shot creative structuring — propose
7 modules from scratch; more coverage tends to read as better, which is exactly the axis sol
won on (see Test 2 below). Wrap-up is closer to careful instruction-following: cross-reference
a transcript against an *existing* doc so nothing already-known gets restated as still-to-do,
and make a real judgment call (was this module reasonably covered — continue or advance?)
inside a strict four-section format. Sol's demonstrated strength doesn't obviously transfer to
that skill, and nothing tested it there.

**Decision: leave on `gpt-5.6-luna`.** No comparison harness exists yet for this prompt
(`scripts/compare_outline_models.py` is outline-specific — it drives the setup flow, not a full
lesson session). Building one and running it is the natural next step *if* there's a concrete
reason to suspect a quality problem — not speculatively, given the cost asymmetry above.

---

## Test history

### Test 1 — 2026-08-07 — `course-outline-proposal` + `wrap_up_model`: `gpt-5.4-pro` vs `gpt-5.6-luna`

**Method:** 8 fixed profiles (2 rounds — software-adjacent, then healthcare/small-business/
education/creative/finance), `scripts/compare_outline_models.py`, quality judged by eye.

**Result:** Luna 12-24x faster (3.7-7.2s vs 52.5-129.1s wall time) with no quality regression on
any profile — in 3 of 8 cases luna's outline was arguably *more* tailored (added a domain-specific
or capstone module gpt-5.4-pro's outline lacked), never the reverse.

**Decision: switched.** Both `course-outline-proposal.md` and `wrap_up_model` moved to
`gpt-5.6-luna`. Full writeup: [architecture-decisions.md §5](architecture-decisions.md).

### Test 2 — 2026-09-17 — `course-outline-proposal`: `gpt-5.6-luna` vs `gpt-5.6-sol`

**Method:** Same 8 profiles, `scripts/compare_outline_models.py --models gpt-5.6-luna,gpt-5.6-sol`.

**Result:**
- Latency: comparable (~4.6s vs ~5.5s avg total) — negligible for a once-per-learner step.
- Cost: sol is ~17-20x more per token, but ~$0.0005 → ~$0.008 per learner in absolute terms —
  economically irrelevant at this call frequency.
- Quality: sol included one more genuinely relevant module in about half the profiles that
  luna's outline missed entirely — a dedicated safety/reliability module for an LLM-features PM
  course, effect sizes/NNT for a nurse/statistics course, a data-cleanup module for a VBA course,
  and a gentler on-ramp for a non-technical SQL learner. No profile favored luna.

**Decision: switched.** `course-outline-proposal.md` → `gpt-5.6-sol`
(`config/model_presets/course-outline-sol.json`). `make smoke` 11/11 after the switch.

### Test 3 — 2026-09-17 — `course-outline-proposal`: `gpt-5.6-sol` vs `gpt-6-astra`

**Method:** Same 8 profiles, `scripts/compare_outline_models.py --models gpt-5.6-sol,gpt-6-astra`.
Rationale for testing astra here specifically (not elsewhere): outline is the one place in the
app where the run-once-per-learner economics make even the priciest model's absolute cost
negligible, so it's the lowest-risk place to check whether paying more buys anything.

**Result:**
- Latency: astra ~32% slower (~5.8s vs ~7.7s avg total) — consistent regression, not noise.
- Content: no consistent quality win for astra. It produced *fewer* modules than sol in 5 of 8
  profiles (6 vs 7), occasionally dropping something sol had (a validation/sharing-safely step
  for the non-technical SQL learner; a dedicated regression/confounding module for the nurse
  course).
- **Real downside, not just a wash:** astra repeatedly bakes the learner's stated *session*
  length into individual *module* descriptions ("In 30 minutes, get comfortable with
  DataFrames...", repeated per-module in some profiles — worst case, backend-pandas, every one
  of 7 modules). This directly conflicts with how the app actually works: one session routinely
  does *not* finish one module (see same-module resume, shipped 2026-09-17) — astra's outlines
  imply a false one-session-per-module promise that sol's never make.

**Decision: rejected, stayed on `gpt-5.6-sol`.** No cost concern (still ~$0.03/learner even at
astra's price) — rejected purely on latency + the module/session-length conflation, with no
offsetting quality gain to justify either.

---

## How to run the next comparison

```bash
python3 scripts/apply_model_preset.py --list                       # see existing presets
python3 scripts/compare_outline_models.py --models a,b             # outline-turn candidates only
```

For a task other than `course-outline-proposal`, `scripts/compare_outline_models.py` doesn't
apply as-is — it's hardcoded to the setup/outline flow (see its docstring's "Reuse plan"). A
`wrap_up_model` comparison needs an analogous script that drives a full lesson session (or
replays a real one) through both candidates and diffs the resulting progress docs — not yet
built; build it when there's a concrete reason to test, not speculatively (see the "why it's
still on luna" section above).

After any switch: update the "Current configuration" table above, add a dated entry under
"Test history" (even — especially — for a rejected candidate), and commit
`config/model_presets/<name>.json` alongside the prompt file change so the decision and the
mechanism that applied it stay together.
