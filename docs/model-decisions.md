# Model Decisions

Which model each task uses, why, and the test history behind each choice. Both OpenAI and
Anthropic (Claude) are available providers as of 2026-09-29 — see "Claude as a second
provider" below.
Complements `docs/prompts.md` "Model presets" (the mechanism — `config/model_presets/`,
`scripts/apply_model_preset.py`) and `docs/roadmap.md` (open/in-progress items link back
here once a comparison actually runs). This file is the durable record of *what we tried
and why we landed where we did* — update it whenever a model comparison runs, whether or
not it results in a switch. A rejected candidate is exactly as worth recording as an
adopted one, so nobody re-runs the same comparison cold next quarter.

---

## Current configuration

Reference point: `config/model_presets/baseline-2026-09.json` +
`course-outline-claude-sonnet-5-5.json` (see `docs/prompts.md`). Pricing:
`app/domain/pricing.py`, refreshed 2026-09-30. `course-outline-sol.json` stays on disk as the
prior decision's record but is no longer the applied preset.

| Task (prompt slug) | Model | Why this tier | Last reviewed |
|---|---|---|---|
| `course-session-init` | `gpt-4.1` | Chat turn, latency-critical (learner is waiting live) | 2026-09-17 (prompt rewritten; model unchanged, not re-tested) |
| `course-session-core` | `gpt-4.1` | Chat turn, latency-critical | 2026-09-17 (prompt rewritten; model unchanged, not re-tested) |
| `course-session-closure` | `gpt-4.1` | Chat turn, latency-critical | 2026-09-17 (prompt rewritten; model unchanged, not re-tested) |
| `user-profile-collection` | `gpt-4.1` | Plain framing Q&A, no creative work — split off the outline turn specifically so this could run on a cheap/fast tier (roadmap item 1, 2026-08-04) | 2026-08-04 |
| `user-profile-extraction` | `gpt-5.4-mini` | Structured extraction from a short transcript | not re-tested since introduced |
| `course-outline-extraction` | `gpt-5.4-mini` | Structured extraction from a short transcript | not re-tested since introduced |
| `course-outline-proposal` | **`claude-sonnet-5-5`** | Beat `gpt-5.6-sol` on quality, latency, *and* cost across an 8-profile comparison — no tradeoff to weigh | **2026-09-30** — see [Test 5](#test-5-2026-09-30--course-outline-proposal-gpt-56-sol-vs-claude-sonnet-55-vs-claude-opus-55) |
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

### Test 4 — 2026-09-17 — `course-outline-proposal`: `gpt-5.6-luna` vs `gpt-5.6-terra` vs `gpt-5.6-sol`

**Method:** Same 8 profiles, three-way:
`scripts/compare_outline_models.py --models gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol`. Terra
("roughly the mini tier" per its own model page, vs sol's "unsuffixed/flagship tier") hadn't
been considered — checked since it's cheap to verify with the harness already built.

**Result:**
- Latency: terra consistently between luna and sol (~6.3s avg total this run vs sol's ~6.9s,
  which ran unusually high due to one 11.1s outlier — sol's Test 2 average was ~5.5s, so treat
  both as roughly comparable rather than reading too much into this run's exact gap).
- Quality: genuinely mixed, not a clean win either way.
  - Terra matched sol's earlier win over luna in 2 profiles: nurse-stats (terra also separates
    out a statistical-vs-clinical-significance/NNT module) and financial-VBA (terra adds its own
    "Importing, Cleaning, and Consolidating Data" module).
  - Terra did something *neither* luna nor sol did in backend-pandas: added "Efficient, Safe
    Analysis at Scale" (vectorization, when pandas stops being the right tool).
  - But terra dropped a module both luna and sol had in marketing-SQL (6 vs 7 — missing the
    validate/share-safely step, the same pattern Test 3 saw from astra), and trailed sol by one
    module in 3 others (bakery, teacher-python, designer-frontend), each time missing something
    sol's outline included (maintenance/backups, tool polish, accessibility as its own step).

**Decision: no change, stayed on `gpt-5.6-sol`.** Terra is a real contender — closer to sol than
its "mini-tier" positioning suggested — but inconsistent (strong in 3/8 profiles, thinner in
4/8), while sol matched-or-beat both alternatives' completeness in every profile across Tests
2-4. Cost isn't a factor either way at outline's volume (once per learner), so there's no reason
to trade sol's consistency for terra's occasional wins. Worth a full re-test with a larger
profile set if a future comparison suggests terra's variance was this-run noise, not a real
gap — not warranted from a single 8-profile pass.

### Test 5 — 2026-09-30 — `course-outline-proposal`: `gpt-5.6-sol` vs. `claude-sonnet-5-5` vs. `claude-opus-5-5`

**Method:** Same 8 profiles, two passes with `scripts/compare_outline_models.py`
(provider-agnostic already — no script change needed). First pass tested `claude-sonnet-5`
and `claude-opus-5`; mid-comparison, `GET /v1/models` on the live account surfaced a newer
generation (`claude-sonnet-5-5` released 2026-09-28, `claude-opus-5-5` released 2026-09-21)
not yet in this repo's registry or in the bundled pricing reference — added to
`model_registry.py` and `pricing.py` (confirmed live against anthropic.com/pricing: opus-5.5
is $4/$20/MTok, *cheaper* than opus-5's $5/$25, not a same-price successor; sonnet-5.5 is
$2/$10/MTok, unchanged from sonnet-5), then re-ran the full 8 profiles against
`gpt-5.6-sol,claude-opus-5-5,claude-sonnet-5-5`.

**Result:**
- Quality: sol's one consistent edge across Tests 2-4 was an explicit closing
  "validate before you trust it" module (missing from the first-pass claude-sonnet-5/opus-5
  outlines on 2 of 4 profiles checked). The 5.5 generation closed that gap — both
  claude-opus-5-5 and claude-sonnet-5-5 now include it in every profile (e.g. marketing-SQL's
  "Checking Your Numbers: Spot common mistakes such as double-counting and missing data, so
  you can trust your reports before you share them" — near-identical framing to sol's own).
  claude-sonnet-5-5 added value sol never produced in any of Tests 1-4: a dedicated study-design
  module (RCT/cohort/case-control) for nurse-research-statistics; an XLOOKUP/VLOOKUP module for
  bakery-owner-spreadsheets solving the learner's actual "one ingredient price change should
  update every recipe" problem; explicit balance-check/variance-flag language for
  financial-analyst-vba-modeling, plus picking the test persona's own name up into the course
  title. claude-opus-5-5 was comparably strong but didn't add anything claude-sonnet-5-5 lacked.
- Latency: claude-sonnet-5-5 matched or beat sol on every profile (e.g. 5.7s vs. sol's 9.5s on
  teacher-python; 6.8s vs. sol's 7.0s on bakery). claude-opus-5-5 was consistently *slower* than
  sol — up to 16.2s on financial-VBA (sol: 9.2s) — a real regression for a turn the learner
  waits on live.
- Cost: claude-sonnet-5-5 is $2/$10 vs. sol's $4/$20 — half price. claude-opus-5-5 is $4/$20 —
  identical to sol, so its extra latency bought nothing on price.

**Decision: switched.** `course-outline-proposal.md` → `claude-sonnet-5-5`
(`config/model_presets/course-outline-claude-sonnet-5-5.json`). Won on quality, latency, and
cost simultaneously — no tradeoff to weigh, unlike every prior switch in this file. Verified
live end-to-end post-switch: a real setup-flow run (no `model_slug` override — relying purely
on the prompt's own `model:` frontmatter) resolved to `claude-sonnet-5-5`.

---

## Claude as a second provider (added 2026-09-29)

`app/infra/llm_router.py` routes each call to OpenAI or Anthropic by the model slug's
`provider` field in `model_registry.py` — the two providers are interchangeable from every
call site's point of view, including the preset mechanism below. **Verified directly:**
`scripts/apply_model_preset.py --dry-run` against a throwaway preset assigning
`claude-haiku-4-5` to a prompt behaved identically to an OpenAI slug (frontmatter rewrite +
settings-line printout) — the script never validates or special-cases the slug string, so
no code change was needed to support a Claude preset.

**Outline tier decided (2026-09-30) — see [Test 5](#test-5-2026-09-30--course-outline-proposal-gpt-56-sol-vs-claude-sonnet-55-vs-claude-opus-55):**
`course-outline-proposal` switched to `claude-sonnet-5-5`. The remaining tiers below are
still open — same process (compare against the current baseline row, judge quality, check
cost), not a default to assume:

- **Chat-latency tier** — `course-session-init`, `course-session-core`,
  `course-session-closure`, `user-profile-collection` (currently `gpt-4.1`). Candidate:
  `claude-sonnet-5-5` or `claude-haiku-4-5`.
- **Structured-extraction tier** — `user-profile-extraction`, `course-outline-extraction`
  (currently `gpt-5.4-mini`). Candidate: `claude-haiku-4-5`.
- **Guard tier** — `lesson-objective-complete`, `session-length-extraction`,
  `closure-continue-extraction`, `framing-answer-check` (currently `gpt-5.4-nano`).
  Candidate: `claude-haiku-4-5`.
- **`wrap_up_model`** (progress synthesis, currently `gpt-5.6-luna`). Candidate:
  `claude-haiku-4-5` or `claude-sonnet-5-5`. No comparison script exists yet for this one
  either (same gap noted below for luna vs. sol) — needs the same "drive a real session,
  diff the resulting progress doc" tool before a Claude candidate can be judged here.

Before testing any of the above, re-check `GET /v1/models` on the live account first —
Test 5 found a newer Claude generation (5.5) mid-comparison that wasn't in this file, the
bundled model reference, or `model_registry.py`/`pricing.py` yet; don't assume the models
already registered here are still the latest available.

Once a tier's candidate wins (or loses — record that too), add it to a new
`config/model_presets/<slug>-<model>.json` (mirroring `course-outline-claude-sonnet-5-5.json`'s
shape — one prompt, applied on top of baseline) and to the "Current configuration" table
above. `baseline-2026-09.json` stays on disk unchanged regardless — reverting any one prompt
is always `apply_model_preset.py baseline-2026-09`.

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
