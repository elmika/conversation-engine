# Roadmap — Improvements & Known Issues

Tracks improvement items surfaced by manual/exploratory testing that aren't yet scheduled work.
Not a feature list (see `docs/features.md`) and not an API contract (see `docs/openapi.yml`) — this is a backlog.

---

## From: manual E2E smoke test, 2026-08-03

Full simple learning flow tested live via `make up` + Chrome (new user → setup → course suggestion →
Module 1 intro → core exchange → End Session). Functionally the flow worked end-to-end with no
errors and good content quality. Two issues surfaced:

### 1. Setup flow pinned to `gpt-5.4-pro` — high cost, high latency (priority: high) — ✅ Shipped 2026-08-04

Implemented as designed below: `prompts/user-profile-collection.md` now covers only the 4 framing
questions on `gpt-4.1`; a new `prompts/course-outline-proposal.md` (still `gpt-5.4-pro`) handles
just the outline turn. Phase switching is code-owned via `app/domain/setup_flow.py` (turn-count
based, mirrors `lesson_flow.py`). Live-verified: framing turns now respond in 1.4–3.5s (vs.
44–140s before); the outline turn still takes ~95-130s on gpt-5.4-pro, which is now isolated to
just that one call instead of all five setup turns.

`prompts/user-profile-collection.md` (the "Setup — Profile & Goal" onboarding prompt) declares
`model: gpt-5.4-pro` — the most expensive model in `app/domain/model_registry.py`. Every other
prompt in the system (`course-session-core`, `course-session-closure`, `course-session-init`,
extraction prompts) uses `gpt-4.1`, `gpt-5.4-mini`, or `gpt-5.4-nano`.

The onboarding conversation is a plain 3–4 turn conversational Q&A (name, industry, motivation,
session length) — it does not need pro-tier reasoning. In the test session this single prompt
was responsible for effectively 100% of API spend:

| Turn | Model | TTFB |
|---|---|---|
| Setup Q1 → Q2 | gpt-5.4-pro | 133.6s |
| Setup Q2 → Q3 | gpt-5.4-pro | 66.3s |
| Setup Q3 → Q4 | gpt-5.4-pro | 44.4s |
| Setup Q4 → course suggestion | gpt-5.4-pro | 138.5s |
| Lesson core turns (×2) | gpt-4.1 | ~1–4s |

Session cost breakdown (14 requests total): `gpt-5.4-pro-2026-03-05` input $0.104 + output $0.381
= **$0.485**; all `gpt-4.1` / other-model calls billed **$0.00**. Latency was also 15–35x worse
than the `gpt-4.1`-backed lesson turns, with one turn showing an unexplained ~2–3 minute gap
between a visible typing indicator and rendered text (likely genuine model latency, not a stream
bug, but worth confirming — see item 2's sibling note).

**Suggested fix — split by phase, don't blanket-downgrade:** `user-profile-collection` currently
does two different jobs under one `model:` binding — turns 1–4 are plain framing Q&A (name,
industry, motivation, session length), and turn 5 is the actual creative output of setup: proposing
the personalised course outline the learner will spend their whole course on. Getting the outline
wrong (mis-scoped modules, wrong difficulty, missed the stated goal) is a much more expensive
mistake than a slow/expensive framing question, so these two jobs shouldn't share a quality tier.

Mirror the pattern the lesson flow already uses (`course-session-init` / `-core` / `-closure` as
separate single-purpose prompts, each with its own `model:`) and split setup into two phases:

- **Framing Q&A (turns 1–4)** → downgrade to `gpt-4.1`, matching every other conversational prompt
  in the registry. No creative/design work happens here, just information gathering.
- **Course outline proposal (turn 5)** → keep on `gpt-5.4-pro` (or re-evaluate against `gpt-5.4-mini`
  head-to-head on outline quality before downgrading) — this is the one generation in the whole
  flow worth paying frontier-tier cost and latency for.

This needs a small architecture change, not just a frontmatter edit: today phases 1 and 2 are the
same prompt/conversation, so they can't carry different models. Splitting into two prompts (e.g.
`user-profile-collection` for the Q&A + a new `course-outline-proposal` for the final turn, handed
off the way `course-session-init` hands off to `-core`) would let each phase carry its own model
while keeping the outline-quality bar exactly where it is today. Re-run the smoke test after the
split to confirm framing-question latency drops to the `gpt-4.1` ballpark while the proposed course
outline is unchanged in quality from this test's baseline.

### 2. Bare `/history` route silently starts a new course session as a side effect (priority: medium)

Navigating directly to `http://localhost:3000/history` (no `/u/{userId}` prefix) does not show a
history page or 404 — it falls through to root-page logic, which auto-provisions/continues state
and calls `POST /conversations/init-stream`, **auto-creating and starting a new course session**
(consuming an LLM call) purely as a side effect of loading the URL. This happened without any
click on "Start next session."

This wasn't hit via normal in-app navigation (the "History" nav tab is the always-present sidebar
list, scoped under `/u/{userId}/...`, and behaves correctly) — only via directly typing/loading the
bare path. Still a real risk: a bookmarked, shared, or browser-autocompleted bare URL could
unknowingly advance a learner's course state and burn an LLM call.

**Suggested fix:** the bare (non-`/u/{id}`-prefixed) top-level routes (`/history`, `/chat`, `/admin`
if applicable) should redirect to the user's existing UUID-scoped route (from `localStorage`, per
the identity model in `docs/features.md` §1.1) or to a neutral landing page — never trigger
conversation/session creation as a side effect of a GET navigation.

### 3. No "please be patient" UI for the course-outline compile step (priority: medium) — ✅ Shipped 2026-08-04

Once item 1 ships (splitting setup into a fast framing-Q&A phase + a deliberately slower,
higher-quality course-outline-compile phase), that one remaining step will still legitimately
take up to ~2 minutes — that's the accepted cost of keeping outline quality on the frontier
model. But today the learner has no way to tell "this is expected" from "this is broken": the
UI shows the same bare three-dot typing indicator used for every other turn, whether the wait is
2 seconds or 2+ minutes (this test session saw one such wait run 133–138s with nothing but that
indicator on screen — see the original 2026-08-03 smoke-test summary).

A learner staring at an unchanging typing indicator for over a minute has every reason to assume
the app has frozen, refresh the page, or give up. `docs/qa-test-suite.md`'s latency requirement
now codifies the expectation explicitly: ordinary turns must respond in ~3s (fail at ~5s), but
the outline compile gets a dedicated allowance of up to ~2 minutes — *conditional on* showing a
distinct patience/progress treatment, not the generic indicator. Waits beyond ~5 minutes should
be flagged regardless of UI treatment (something has actually gone wrong, not just "it's a slow
model").

**Suggested fix:** give the course-outline-compile step its own loading state, distinguishable
from the normal per-turn typing indicator — e.g. reassuring copy ("Compiling your personalised
course — this can take a minute or two"), and ideally something that visibly progresses (elapsed
time, a staged checklist, or similar) rather than a static/looping animation, so a learner can
tell the difference between "still working" and "stuck." Scope this alongside item 1's phase
split, since that's what makes this step's timing predictable enough to design a loading state
around.

**Shipped as:** `frontend/components/chat/CourseOutlineLoadingIndicator.tsx` — spinner + "Compiling
your personalised course… This can take a minute or two." + a live elapsed-seconds counter,
shown whenever the SSE `meta` event reports `prompt_slug: "course-outline-proposal"`
(`frontend/components/chat/StreamingMessage.tsx`). `prompt_slug` is threaded through
`useStreamingChat.ts`'s state machine the same way `model` already was.

**A second, more serious bug surfaced building this:** the new indicator initially never rendered
at all, because `app/api/routes.py`'s streaming `event_generator()` yielded the `meta` SSE frame
and then ran a **blocking synchronous `for` loop** over the OpenAI SDK's streaming generator with
no `await`/`asyncio.to_thread` — monopolizing the asyncio event loop for the entire LLM wait, so
the already-queued `meta` bytes never actually flushed to the socket until the blocking call
finally returned. For `gpt-4.1` (first token in ~1-2s) this was invisible; for `gpt-5.4-pro`
(first token in 95-125s) it meant `meta`, the full response, and `done` all arrived in one burst
at the very end — confirmed via a raw `curl -N` directly against FastAPI, bypassing the frontend
entirely. This affected **all four streaming endpoints**, not just the outline turn — any slow
model on any prompt would have hit the same silent stall. Fixed by bridging the sync generator
through a background thread (`_iter_in_thread()` in `app/api/routes.py`, using
`loop.run_in_executor`) so the event loop stays free to flush queued SSE frames while the LLM
call is in flight. Verified via the same `curl -N` probe: `meta` now arrives within ~1s,
independent of how long the model takes to produce its first token.

---

## Not yet triaged

- Admin panel, conversation download, multi-user/user-switching, and "Start next session"
  continuation were not exercised in the 2026-08-03 smoke test — worth a follow-up pass.
