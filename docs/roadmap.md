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

### 2. Bare `/history` route silently starts a new course session as a side effect (priority: medium) — ✅ Shipped 2026-08-06

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

**Fix shipped:** `/history` now redirects straight to `/u/{userId}/history` (resolving the UUID from
`localStorage` client-side) instead of falling through `/` → `/u/{userId}/chat`. Item 5 below covers
the second, broader entry point into the same failure mode.

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

## From: manual E2E smoke test, 2026-08-06

Ran `docs/qa-test-suite.md` Test 1 (Course Setup) and Test 2 (First Learning Experience) live via
`make up` + Chrome, on a fresh learner. Both tests passed their core scripted steps — framing Q&A
latency was 1.4–3.5s per turn (within the ≤3s/≥5s bands), the course-outline compile showed the
dedicated indicator with a live-incrementing elapsed counter, and lesson content stayed coherent
and personalized across all four exchange turns. Three issues surfaced beyond the script:

### 4. Session-complete card: unrendered markdown + missing module status markers (priority: medium) — ✅ Shipped 2026-08-07

Step 2.6's "Session complete" card (`frontend` — same course-module-list component reused from the
setup outline and mid-lesson header) has two rendering defects not present in the normal chat
bubbles:

- **Module titles render literal `**bold**` asterisks** instead of formatted bold text — e.g.
  `**Pandas for a Backend Engineer** — Build a practical mental model...` shown verbatim, asterisks
  and all. The same titles render correctly (bold, no asterisks) earlier in the same session, both
  in the initial outline proposal (step 1.6) and the mid-lesson module list (step 2.1) — so this is
  specific to whatever component renders the summary card, not the shared markdown renderer used
  elsewhere.
- **No ✓ (completed) / → (next up) markers on any module row** — the spec (`qa-test-suite.md`
  step 2.6) requires the current module checked off and the next one marked up next. The plain
  numbered list (1–7) carries no such markers. Contrast: the ordinary in-chat module list (seen
  right after re-entering the course later in this session) does render `✓ 1. ...` and `→ 2. ...`
  correctly — so the summary card again diverges from the component it's presumably meant to share
  logic with.

The "Where to pick up next time" note itself was accurate (correctly summarized the last topic
covered), and both "Start next session"/"Close" buttons worked. Scope the fix to whatever renders
the Session Complete card specifically — it's drifted from the module-list rendering used
elsewhere, not a markdown-pipeline-wide regression.

**Fix shipped:** two changes, one per bug. (1) `SessionSummaryCard.tsx` now renders each module
title through `ReactMarkdown`/`remarkGfm` (the same pipeline `MessageBubble`/`StreamingMessage`
already use for chat text) instead of dropping it into a raw `<span>`, so `**bold**` renders
correctly. (2) Module completion status wasn't available in the data at all — the in-chat module
list gets its ✓/→ markers from the LLM reading the Progress section live, but the summary card's
`modules` field was just a flat list of titles with no status. `build_session_summary()`
(`app/learning/session_summary.py`) now also scans the Progress section for the highest `Module
N` it names (the same section the LLM is instructed to treat as sole source of truth) and tags
each module `done` / `current` / `upcoming` accordingly; `status` is `null` when the Progress
section names no module (e.g. before the first session). `SessionSummarySchema`/`SessionSummary`
(backend + frontend types), `docs/openapi.yml`, and `docs/postman_collection.json` were updated
to carry `modules: {title, status}[]` instead of `modules: string[]`; `export-conversation.ts`'s
Markdown export was updated to prefix the same ✓/→ markers. Verified: 5 new backend unit tests
(`tests/test_session_summary.py`) + full backend suite (247 passed); frontend `tsc --noEmit`
clean and 43/43 frontend tests pass (including an updated `export-conversation.test.ts` case);
live-verified via Chrome against a real ended conversation on the running stack — the summary
card correctly showed bold module titles and a `→` marker on the in-progress module, matching a
direct `curl` of the `/summary` endpoint.

### 5. Bare `/u/{uuid}` route (no `/chat/{id}`) also auto-starts a new session — item 2's bug is broader than scoped (priority: medium) — ✅ Shipped 2026-08-06

Item 2 above (still open, not yet fixed) documented bare `/history` auto-provisioning a new course
session as a side effect of navigation. Today's run found the same failure mode via a different
bare path: navigating directly to `/u/{uuid}/` (the user-root, no `/chat/{id}` suffix) 404s as
expected, but clicking the in-app **"History"** nav link from that 404 page silently auto-created
and started a **brand-new third course session** (`state: Active`, immediately consuming an LLM
call for the outline generation) rather than navigating to the history list. Confirmed via the
History sidebar going from 2 conversations to 3 with no explicit "start next session" action taken.

This means the fix for item 2, whenever implemented, needs to guard the user-root route family
(`/u/{uuid}` bare, `/u/{uuid}/history`, etc.) generally — not just the single `/history` path
originally observed — since at least two distinct bare-path entry points now reproduce the same
class of unwanted session creation.

**Fix shipped:** two root causes, both closed. (1) The global `NavBar`'s "Chat"/"History" links were
hardcoded to the bare legacy paths (`/chat`, `/history`) instead of the user-scoped ones — now built
from the UUID already in the URL (or `localStorage` as fallback), so clicking "History" from anywhere,
including this page, goes straight to `/u/{userId}/history`. (2) Bare `/u/{uuid}` (no suffix) 404'd
instead of redirecting — added `frontend/app/u/[userId]/page.tsx`, a server-side redirect to
`/u/{userId}/chat` (the canonical default), closing the 404 gap. Verified live: bare `/history` and
the "History" nav link both land on `/u/{userId}/history` with the conversation count unchanged.

### 6. "Let's start" button is visible and enabled from the first setup turn, not just after the outline (priority: low) — ✅ Shipped 2026-08-07

`qa-test-suite.md` step 1.7 implies the "Let's start" button only appears once the course outline
is ready (it's listed as a check *after* step 1.6). In this run the button was already visible and
apparently enabled in the header from the very first "what's your name?" turn, before any outline
existed — it only disappears/becomes a "Stop" control once the outline generation is actually in
flight. Low priority since clicking it early was not tested (unclear if it's actually functional
pre-outline, or just visually present) — worth a quick check of whether it's disabled under the
hood (e.g. a non-obvious `pointer-events`/opacity state that didn't read as "disabled" in a
screenshot) or a genuine dead-click waiting to happen.

**Investigation found this was a genuine dead-click, not just cosmetic.** The button's only
gating was `isSetupConversation` (conversation's flow slug), which stays `"user-profile-collection"`
for the entire setup flow — both the framing Q&A and the outline phase — so there was no
outline-readiness check at all. Worse, the `complete-setup` endpoint itself had no phase guard
either: clicking early would silently run the extraction LLM calls against a partial Q&A
transcript and durably write a garbage `sections/course/<user_id>.md` / `sections/user/<user_id>.md`
(flipping `has_profile` true) and end the conversation — a "succeeds incorrectly" failure, not an
error.

**Fix shipped**, at both layers: (1) Frontend (`ChatShell.tsx`) now also requires
`localMessages` to contain at least `SETUP_FRAMING_TURNS` (4) user messages before rendering the
button — mirrors `FRAMING_TURNS`/`setup_phase_for_turn()` in `app/learning/setup_flow.py`. (2)
Backend (`complete_setup_route` in `app/api/routes.py`) independently recomputes the same
`setup_phase_for_turn()` from the conversation's actual message count and returns 400 if the
framing phase isn't finished — this is the real safety net, since it can't be bypassed by a
direct API call. `docs/openapi.yml` and `docs/postman_collection.json` document the new 400.
Verified: 2 new backend tests (a rejection case + fixing an existing test that unintentionally
relied on the old, ungated behavior) plus the full suite (248 passed); frontend `tsc`/tests
unaffected (43 passed). Live-verified in Chrome end-to-end on the running stack with a fresh
learner: the button stayed hidden through all 4 framing turns and appeared only once the outline
was rendered, matching `qa-test-suite.md` step 1.7 exactly.

---

## From: ICW live demo, 2026-09-18

First public demo. Six real testers scanned the QR within one minute, **all on mobile**. Most
reached the course outline and some corrected it. **None started the first lesson**, so the teaching
loop, which is the actual product, went unseen. Two failures stacked: a last-minute change broke
starting a fresh session with a clean user live on stage, and the app wasn't ready for phones.
The furthest anyone got was one tester reaching the first eval after 27 minutes. One stopped before
the session-length question. Items below are listed in rough priority order. Status was checked
against the repo on 2026-10-02.

### 7. Demo-day bug: couldn't start a new session with a clean user (priority: high) — ✅ Fixed 2026-09-23

**Root cause (confirmed by Mika, 2026-10-02):** the learner UUID had started being stored in
`localStorage` just before the demo. The demo script assumed opening the link always created a new
user. Instead, `/` kept reloading the existing stored learner on the demo device, so every "fresh"
start dropped back into the same user, which derailed the guided run scripted for Miriam. **Fix:**
`/new` (`1bce1dc6`, 09-23) always mints a fresh learner, while `/` intentionally keeps reusing the
stored id so returning learners keep their identity. Demo runners use `/new`, and the learner QR
stays on `/`. **Process fix:** freeze code before a live demo, and run the exact demo script on the
deployed stack after the last deploy.

### 8. Mobile: side panel eats the screen (priority: high) — ✅ Shipped 2026-09-22, re-test pending

Marta's feedback, and true for every tester. Fixed by `ef89724e` (bottom nav replaces the sidebar
below `md`), `e305f1aa` and `45d00d43` (mobile history cards and touch targets). **Still owed:** a full
setup → outline → first-lesson run on a real phone, since nobody completed that path at the demo.

### 9. Learners don't see how to go from the outline to the first lesson (priority: high) — 🔴 Open

Marta's feedback, confirmed in the logs: several testers reviewed or corrected the outline and then
stopped. This is the direct reason nobody reached the teaching part. The "Let's start" button
(item 6) exists but isn't found, and is probably below the fold or off-screen on mobile. Needs an
obvious primary CTA after the outline is accepted, possibly with the tutor's message also telling the
learner what to tap next.

### 10. Admin panel: group by user + DAU stats (priority: medium) — 🔴 Open

The admin conversations view is one row per conversation. Group it by learner, and add daily-active
-user stats. Overlaps with the retention dashboard designed in the vault (cohort engagement), which
is already on par with the usage/cost dashboard for pilot readiness.

### 11. Admin review layer for learner conversations (priority: medium) — 🔴 Open

Admins need a way to review learner conversations, attach notes, and mark a conversation as reviewed,
so pilot feedback is processed systematically rather than by scrolling raw transcripts.

### 12. Rethink the learner panel around one task (priority: medium, needs design) — 🔴 Open

Redesign the learner UI so it focuses on a single task, the ongoing conversation, and drops the
general-purpose chat-app layout. Design first, not a direct build. Should be done with the
learn-with-claude reference-experience work, not separately from it.

### 13. Separate admin from learner identity (priority: medium) — 🔴 Open

Today the admin view sits inside the learner app and goes through a learner `user_id` route. The
admin shouldn't need a learner id at all. Give admin its own entry point that doesn't depend on
learner identity. Related residual gap: NavBar's admin tab visibility (see Not yet triaged).

### 14. Consent: people share personal things (priority: high) — 🟡 Gate shipped 2026-09-23

The demo ran on verbal consent. The consent gate (see Not yet triaged) shipped five days later.
What the demo added: testers talk about personal matters, not just work goals, so the disclosure and
the deferred full-GDPR items (real deletion flow, retention, export) weigh more than the original
plan assumed. Re-read the consent copy with that in mind before the next unsupervised run.

### 15. In-app help: feedback channel, FAQ, instructions (priority: medium) — 🔴 Open

"Where do I give feedback?" There's no place for that today. Add a help space with a feedback
channel, short FAQs, and first-use guidance on how the platform works.

### 16. Show the whole journey: objective, path, what to expect (priority: medium, needs design) — 🔴 Open

Testers didn't know where they were going or what to expect. Show the full course journey, set a
visible objective, and consider light gamification. The within-module checklist (`472a7dda`) is a
first step. Ties to the accountability / "reason to come back" thread in the vault problem spec.

### Ideas to evaluate (from the same debrief, not yet build items)

- **Calendar booking for sessions.** Active practice needs a quiet space and a fixed slot. After setup
  (or at session end), offer to put the next session in the learner's calendar.
- **Voice/audio.** An open product question, not a commitment. One option is to alternate deep
  written exercises with light voice intros or reviews for commute time. Decide the focus-vs-commute
  stance first, and test whether learners ask for audio without being prompted before asking them.
- **Requests for a podcast and for uploading your own content** came up in Q&A. NotebookLM covers
  both well, so this is a positioning signal more than a backlog item.

---

## Not yet triaged

- **Audit SkillForge's agent harness against the 8-component framework (surfaced 2026-09-22,
  priority: low — a consolidation-pass item, not urgent).** Nikki Siapno's "8 Components of
  Harness Engineering" (Context, Memory, Tools, Orchestration, Execution, Guardrails, Tracing,
  Evals — full note: `Areas/AI-LLM-Explorer/research/harness-engineering-8-components-siapno-2026-09.md`
  in the vault) is a clean checklist to map against what SkillForge's backend actually does today.
  Mika wants to internalize this framework, not just file it — read it against something already
  half-known rather than cold, so do this the next time SkillForge's architecture is being
  consolidated or reviewed end-to-end: go component by component, note what exists
  (`app/domain/model_registry.py`? the conversation/session layer? `docs/architecture-decisions.md`?),
  what's missing, and what's implicit-but-undocumented. Not a redesign — a mapping exercise, to
  turn a passive read into a working audit.

- **GDPR: no consent gate before a learner's personal data is collected (surfaced
  2026-09-17, priority: high — the 2026-09-18 ICW demo QR sends real strangers straight in). —
  ✅ Shipped 2026-09-23.** All three items below landed, not just the frontend-gate minimum:
  the consent screen (`frontend/components/ConsentScreen.tsx`, wired into
  `frontend/app/page.tsx`) using the disclosure copy verbatim; a `consent_records` table
  (`app/infra/persistence/models.py::ConsentRecord`, `app/infra/persistence/repo_consent.py`)
  recording consent timestamped and keyed to `user_id` via `GET`/`POST /u/{user_id}/consent`;
  and server-side enforcement (`require_consent` dependency in `app/api/routes.py`, wired into
  all three conversation-creation routes) rejecting any `user_id` with no recorded consent
  (403), independent of the frontend. `docs/openapi.yml`, `docs/postman_collection.json`, and
  `docs/features.md` (§1.7) updated; `tests/test_consent.py` covers the gate directly, and
  `tests/conftest.py` bypasses it by default for every other test via
  `app.dependency_overrides` so existing conversation-creation tests didn't need touching.
  Verified live: fresh-UUID click-through shows the gate and blocks progress until checked;
  an already-consented UUID skips straight to chat on reload; direct `curl` against a
  never-consented `user_id` confirms the 403. Still deferred, as scoped — see "Not in this
  pass" below: data export, a real deletion flow, the full GDPR rights list, DPA language,
  EU-residency confirmation.

  Original flow (`frontend/app/page.tsx` → `getOrCreateUserId()`) silently minted a UUID and
  redirects straight into chat, no screen of any kind. From the first framing question on, the
  platform collects the learner's **name, role/industry, stated goal**, and the **full
  conversation transcript** of every session, later synthesized into progress notes. All of it
  is admin-visible per learner — `AdminConversationsTable` shows name + full message content,
  one row per conversation. Today none of this is disclosed anywhere before it happens.

  **Decided with Mika (2026-09-17): minimal consent gate before tomorrow's demo**, not a full
  GDPR pass (that's a separate, later item — data export, deletion-on-request flow, formal
  retention policy, DPA language for OpenAI as processor).

  Minimal scope for tomorrow:
  1. **A consent screen inserted before the UUID→chat redirect** — short disclosure + a
     checkbox, "Continue" disabled until checked. Suggested copy (Mika should review/edit
     before it ships, this is a draft, not final legal text):

     > Before we start: SkillForge is a live pilot, not a finished product. To personalise
     > your course we'll ask your name, role, and what you want to learn — and everything you
     > write in a session is saved so the tutor can pick up where you left off next time. As
     > the person running this pilot, I can see your name and messages to build and improve
     > the product; nobody else does. Your messages are sent to OpenAI to generate the
     > tutor's replies, same as any AI chat tool. Nothing is sold or shared beyond that. This
     > pilot is provided as-is, with no guarantee of availability, and I may end it at any time
     > without needing to justify why. It's expected to run for around two weeks — enough time
     > to complete one course. After the pilot, I may keep an anonymized version of session
     > content to improve the product. You can ask for your data to be deleted at any time —
     > mikael.baron@squaredpoint.com.
     >
     > ☐ I understand and agree to this.

     Notes:
     - The "around two weeks" line doubles as the retention-period disclosure flagged as
       missing below — a concrete criterion (pilot duration / one course's length) rather than
       an open-ended "we keep it forever."
     - **"Anonymized" is disclosed honestly here, but its real strength is limited — say so
       plainly, don't let the word imply more protection than it delivers.** For a small
       in-person pilot (ICW attendees Mika knows personally), stripping the name field doesn't
       make a transcript unlinkable: 1-2 lines about someone's actual job/role is often enough
       to re-identify them anyway, on top of Mika knowing who was in the room. This is
       pseudonymization at best, not true anonymization — GDPR treats those very differently
       (pseudonymized data is still personal data). Considered and explicitly rejected: asking
       "what should I call you?" (nickname) instead of "what's your name?" — doesn't reduce
       what's collected (most people give their real name anyway) and doesn't change the
       re-identification risk above; dropped as a non-fix, not worth prompt-wording changes.
     - Still doesn't cover the full rights list (access, portability, objection, withdrawal,
       complaint to a supervisory authority) — those remain deferred to the full GDPR pass.

  2. **Record consent server-side, timestamped, tied to `user_id`** — not just a `localStorage`
     flag. A `localStorage`-only record can't be produced as evidence that consent was actually
     given if ever asked. Exact schema (new table vs. a column) is an implementation call for
     whoever builds this — just needs to be queryable later ("did user X consent, and when").
  3. **Ideal but not a blocker for tomorrow:** have the backend reject conversation creation for
     a `user_id` with no recorded consent, not just hide the UI. Defense in depth against
     someone hitting the API directly, bypassing the frontend gate. If time-constrained before
     the demo, ship the frontend gate + server-side record first; add backend enforcement after
     if there isn't time tonight.

  **Not in this pass** (full GDPR item, later): data export/download for a learner, a real
  deletion-on-request flow (today "ask for deletion" has no implementation behind it — the
  draft copy above promises something that doesn't exist yet), retention period decision,
  whether OpenAI's data-processing terms need a formal DPA reference in the copy. Data
  residency note for whenever the full pass happens: the Fly backend runs in `cdg` (Paris) —
  worth confirming as an EU-residency fact in the eventual real privacy policy, not asserting
  it without re-checking `fly status -a learning-platform` at that time.

- **✅ Shipped 2026-09-17 — Learner-facing prompt/model override removed (security gap).**
  Mika noticed the chat header still showed prompt and model selector dropdowns and asked
  to plan what to do with them — turned out to be a real gap, not just clutter: the
  underlying request fields (`prompt_slug`/`model_slug` on `ConversationRequest`,
  `InitSessionRequest`, `ConversationRewindRequest`) had no server-side authorization check,
  so any caller (not just the UI) could force an arbitrary prompt or an expensive model tier
  on every turn. Fixed by removing these fields from the learner-facing schemas entirely
  (not just ignoring them) and deriving the setup-vs-course-session choice server-side from
  profile state on `init-stream`. Internal test/comparison tooling that legitimately needs to
  override either (`scripts/compare_outline_models.py`, `scripts/smoke_lesson_lifecycle.py`,
  several pytest integration tests) now goes through a mirrored `/admin/u/{userId}/...` route
  set gated by the existing admin bearer token. Frontend: `ModelSelector`/`PromptSelector`
  components and their Zustand store fields removed from the chat header entirely — matches
  the "code owns deterministic state, never client input" principle the lesson/setup phase
  orchestrators already follow, and removes the dead UI clutter Mika flagged.
  Verified: full backend suite (280, incl. 4 new regression tests specifically covering the
  gap and its fix), frontend suite (43), `make smoke` (11/11), live browser check (no
  selectors, zero console errors, normal turns unaffected), and a live run of both scripts
  against the new admin routes. `docs/openapi.yml` and `docs/postman_collection.json` updated
  (new `AdminConversationRequest`/`AdminInitSessionRequest` schemas + 4 new admin paths).
  Not done in this pass: `GET /prompts`/`GET /models` are still unauthenticated (pre-existing,
  separately-tracked gap below) — nothing in the learner UI calls them anymore, but the admin
  panel's own prompt/model management pages still do, so gating them needs those pages' fetch
  calls updated to attach the admin token first; deferred to avoid breaking the admin panel
  in this same pass.

- **Naming: usage-ceiling "session" scope should be "conversation" (surfaced 2026-09-17).**
  Confirmed while discussing spend-cap margin with Mika: the `session` cap scope
  (`app/domain/usage_ceiling.py`, `Settings.session_spend_cap_usd`, `get_session_spend_usd`,
  `session_cap_usd`/`session_spend_usd` params in `services.py`/`routes.py`) is keyed on
  `conversation_id`, and each class sitting (and setup) gets its own fresh conversation — so the
  cap already behaves as "per class," matching what Mika meant by "per session." The code name is
  the confusing part: "session" reads as ambiguous against a login/HTTP session to anyone new to
  the codebase. Mika asked to rename the scope/identifiers to `conversation` (`CapScope` literal,
  `Settings.conversation_spend_cap_usd`, `get_conversation_spend_usd`, etc.) for semantic clarity —
  pure rename, no behavior change. **Leave learner-facing copy in `CAP_MESSAGES` saying "session"**
  — that's correct from the learner's point of view (they call a class a session); only the
  internal code identifiers are the confusion risk.
- **Model-tier review starting 2026-09-17** — full current configuration, rationale per task,
  and the test-by-test history (what was compared, why, and the decision) now live in
  `docs/model-decisions.md`, not here. Summary: `app/domain/pricing.py` and
  `app/domain/model_registry.py` refreshed against live OpenAI data;
  `course-outline-proposal` switched `gpt-5.6-luna` → `gpt-5.6-sol` after a head-to-head;
  `gpt-6-astra` tested and rejected for the same task (slower, no quality win, and its
  outlines conflict with the same-module-resume architecture below); `wrap_up_model`
  deliberately left untested/unswitched — see `docs/model-decisions.md` for why.
- Admin panel, conversation download, multi-user/user-switching, and "Start next session"
  continuation were not exercised in the 2026-08-03 smoke test — worth a follow-up pass.
- `course-session-core` (the lesson's Core moment) interaction-quality regression —
  **✅ Shipped 2026-09-17** (`docs/socratic-tutor-plan.md` Step 1): short ask→answer→
  acknowledge-and-extend exchanges (avg 297→47 words/turn on gpt-4.1), plus a dynamic
  objective-guard min-turns and a softened, continuable closure
  (`app/learning/closure_continuation.py`). Live-dogfooded 2026-09-17, quality confirmed good
  without any model-tier change. See `docs/tutor-behavior-checklist.md` for the behavior spec
  this should be checked against on future prompt/model changes.
- `course-session-init` (the lesson's opening message) was overwhelming — the full per-module
  outline (every module's description, not just the current one) plus two redundant
  "pick up here" / "do this now" lines buried the actually-good explanatory paragraph.
  **✅ Shipped 2026-09-17**: module list now shows the description only for the current (→)
  module; the two redundant one-liners are gone — straight from the paragraph to the
  session-length question. Feedback from Mika's live dogfooding session, same day as the
  `course-session-core` ship above.
- **Idea, not yet built: a place to read the full course outline.** Trimming the opening
  message (above) means the full per-module descriptions are no longer shown anywhere after
  the initial setup/outline-proposal turn. Surfaced 2026-09-17 alongside the opening-message
  trim — needs its own design (a "View full outline" link/modal? a course detail page?), not
  bundled with the prompt trim itself.
- **Bug: setup framing sometimes never asks the session-length question at all —
  ✅ Shipped 2026-09-17.** Root cause: `setup_flow.py::setup_phase_for_turn` counted raw
  learner turns assuming a strict 1:1 mapping to the fixed 4-question sequence (name, work,
  motivation, session length). A learner's clarifying question back to the tutor ("What skill
  are you talking about?") consumed a turn slot without answering anything, so their *next*
  reply (the real answer) landed on turn 4 — the threshold — and the flow jumped straight to
  the outline, having silently skipped session length. This is also what the
  "`course-session-init` doesn't pick up the desired session length" report from earlier the
  same day actually was — the question was never asked, not mis-parsed. Reproduced exactly
  from Mika's shared transcript. Fix: `app/learning/framing_answer_check.py` (new, cheap-model
  YES/NO check, same shape as the session-length/closure-continuation extractors) runs after
  each framing turn; on NO, bumps a new per-conversation `framing_turns_required` counter
  (`conversations.framing_turns_required`, migration in `app/infra/migrations.py`) so the flow
  needs one more real answer before it can advance — `setup_phase_for_turn` now takes this as
  a parameter instead of hardcoding `FRAMING_TURNS`. Verified: `tests/test_framing_extension.py`
  (including the exact reported sequence), full backend suite (276), `make smoke` (11/11), and
  a live API repro of Mika's transcript end to end (clarifying question → session-length
  question now correctly asked → outline only fires after it's answered).
- **Idea to evaluate (not for the 2026-09-18 demo): fill-in-the-blank / sentence-completion
  questioning** — posing a check-understanding question as an incomplete sentence for the
  student to finish, instead of an open "what do you think?". Surfaced 2026-09-17 alongside the
  ask→answer→extend pattern above but deliberately not bundled with it — needs its own dogfooding
  before it's trusted in a live session; too easy to make sound gimmicky or force an answer shape
  that doesn't fit the actual concept being checked.
- `course-session-closure` (the lesson's Closure moment) — **✅ Shipped 2026-09-17** alongside the
  `course-session-core` rewrite above: closure is now a suggestion rather than a cutoff (learner
  saying "let's keep going" resumes core instead of getting stuck in a repeating wrap-up), see
  `app/learning/closure_continuation.py`.
- **`GET /prompts` (list) stays unauthenticated** — accepted residual gap from Piece C's admin
  auth (2026-09-16). Originally blocked on `frontend/components/chat/PromptSelector.tsx` (the
  learner-facing persona dropdown) depending on it — **that dropdown is gone as of 2026-09-17**
  (see the prompt/model override fix above), so the only remaining caller is the admin panel's
  own prompt-management pages (`app/admin/page.tsx`, `PromptDialog.tsx`'s model dropdown via
  `GET /models`). Gating both behind `require_admin` is now realistic — it just needs those
  admin-panel fetch calls updated to attach the admin token first (they currently don't, since
  the endpoints are open). Not done in the override-removal pass to keep that change scoped;
  net effect meanwhile is unchanged: prompt `system_prompt` text is readable without auth by
  anyone who can reach the API. Acceptable for the pilot's threat model (no sensitive data in
  prompt text today) but worth closing before this becomes a general-purpose multi-tenant
  product.
- **NavBar's "Admin" tab visibility is presence-only, not live-revalidated** — accepted residual
  gap from Piece C2 (2026-09-16). It checks `getAdminToken()` presence in `sessionStorage`, not
  a real backend check, for performance/simplicity (a live check would mean an extra request on
  every page navigation for every learner). A stale/rotated token can show the tab briefly to
  someone no longer actually authorized; harmless, since `/admin*`'s real gate (`AdminTokenGate`)
  still fully re-validates against the backend on every mount regardless of what the nav shows —
  this is cosmetic only, never the actual security boundary.

### Testing harness gaps (surfaced 2026-08-07)

`docs/architecture-decisions.md` §4 splits prompt-behavior testing into B(i) recorded/golden
replay and B(ii) live smoke harness. Only B(ii) is built, and it doesn't cover everything the
strategy implies it should:

- **B(i) golden/recorded replay — decided 2026-06-24, never started.** Right now B(ii) (`make
  smoke`, on-demand only) is the *only* automated coverage of prompt behavior; nothing catches a
  prompt regression between manual runs. This is the highest-priority harness gap since it's a
  committed decision with zero implementation, not just an uncovered edge case.
- **`make smoke` (`scripts/smoke_lesson_lifecycle.py`) only exercises the objective-guard closure
  path** (11/11 against "the objective path" per §4) — the *other* closure trigger, session
  time-over, is untested by the automated harness and only ever hit incidentally during manual
  Chrome runs. A time-over closure regression would not be caught by `make smoke`.
- **No automated harness catches a recurrence of the `course-session-core`/`course-session-closure`
  quality regression fixed 2026-09-17** (see the shipped entries above). Neither B(i) nor B(ii) as
  currently scoped is designed to assert on interaction quality specifically — `make smoke` asserts
  on *shape*, not content quality (per §4). `docs/tutor-behavior-checklist.md` is a manual spec to
  check future prompt/model changes against, not an automated regression gate — a fixed regression
  could still silently reappear with nothing catching it automatically.

### Infra & ops backlog (rescued from `RISKS-AND-IMPROVEMENTS.md`, 2026-08-07)

That file predated the `docs/` convention (last touched 4 months ago) and had drifted out of
sight — its "Done" items are already reflected in `docs/build-status.md`; what's below is what's
still genuinely open. File deleted, content folded in here so it stays visible.

**Deployment & operability — the biggest gaps, nothing here today:**
- No deployment pipeline: no CI/CD, no automated tests on push, no staging environment. Everything
  runs locally.
- No dedicated monitoring/metrics (e.g. Prometheus, tracing/APM). Only structured request logs
  (`request_id`, endpoint, status, latency) exist — fine for reasoning about one request after the
  fact, not for noticing degradation before a learner reports it.
- No alerting on top of those logs — nothing pages anyone if the service degrades or errors spike.
- SQLite is fine for local/demo but has no backup story and limited write concurrency; a real
  database (e.g. Postgres) is the recommended move once this runs unattended.

**Streaming robustness:**
- No backpressure/throttling on outbound SSE events, and the OpenAI stream iteration still runs on
  the event loop inside `event_generator()` — fine at demo load, may not hold under concurrent
  streams.
- Error payloads use one generic `http_error` type — no `validation_error`/`rate_limit` granularity,
  no `retry_after` hint, no partial-content recovery if a stream fails mid-way.
- Two streaming entrypoints (`POST /conversations/stream` and `.../{id}/stream`) share an SSE
  contract by convention only — no shared code/test enforcing they can't drift apart.

**Input & resilience:**
- Input cap (`max_input_chars`) is character-based, not token-based — no real token-budget
  enforcement across history + new turn.
- OpenAI SDK timeout handling has known quirks (not always honoured); worth wrapping in
  `asyncio.wait_for` if this becomes a real problem under load.
- Retry-on-transient-error restarts the stream from scratch; the client sees a new connection, not
  a resume — acceptable today, worth documenting as a known limitation at minimum.

**Testing gaps outside the prompt-behavior harness (see the testing-harness section above):**
- No opt-in smoke test that hits the real OpenAI API directly (as opposed to `make smoke`, which
  exercises the app's own endpoints) — would catch upstream contract drift (e.g. Responses API
  payload shape changes) that mocked tests can't see.
- Not validated against OpenAI's published OpenAPI spec — payload shape is only protected by an
  internal snapshot test today.

**Lower priority:**
- No lint/test guardrail preventing an accidental synchronous DB call on the event loop (currently
  enforced by convention only — `asyncio.to_thread` around every DB op in routes).
- Still targeting Python 3.9 (`Optional[...]`, `UP045` ignored) — revisit when there's a reason to
  drop it.

### Evaluate GPT-5.6 Luna as a replacement for `gpt-5.4-pro` on the two pro-tier calls (priority: medium) — ✅ Shipped 2026-08-07

Surfaced 2026-08-05 from an OpenAI pricing observation (see
`Areas/AI-LLM-Explorer/notes/model-pricing.md`): OpenAI cut GPT-5.6 Luna to **$0.20 input /
$1.20 output** per million tokens — cheaper than `gpt-4.1` ($2.50/$10.00, the flat rate this
codebase already uses for every framing/lesson-turn call) and dramatically cheaper than
`gpt-5.4-pro`, the model item 1 above deliberately kept pinned to the two calls judged worth
paying frontier-tier cost for: `prompts/course-outline-proposal.md` (`model: gpt-5.4-pro`) and
`wrap_up_model` (session-end synthesis, also `gpt-5.4-pro` per `CLAUDE.md`).

Item 1 already downgraded every non-critical call to `gpt-4.1`/mini/nano; these two are the
calls that were deliberately *not* downgraded, on quality grounds — so this isn't a "switch the
cheap stuff" pass, it's a "does the new cheap-and-recent tier now beat the model we kept for
quality reasons" question.

**Not a blind swap.** `gpt-5.6` isn't in `app/domain/model_registry.py` yet (registry tops out
at `gpt-5.4`) — adding it is step 1. Step 2, before touching either prompt's `model:` field, is
a head-to-head on outline quality specifically (same bar the roadmap already set for evaluating
`gpt-5.4-mini` against `gpt-5.4-pro`, never done): does Luna's course-outline output hold up
against `gpt-5.4-pro`'s on a fixed set of test profiles? Luna's price positions it as a
high-volume/low-cost tier (per the OpenAI announcement), which doesn't necessarily mean
frontier-tier reasoning quality — unverified either way as of this writing.

**Steps:**
1. Add `gpt-5.6-luna` (naming per OpenAI's actual model-slug convention — verify) to
   `model_registry.py`.
2. Run the same outline-quality comparison the roadmap already flagged as owed for
   `gpt-5.4-mini` — extend it to include Luna.
3. If quality holds, switch `course-outline-proposal.md`'s `model:` field and `wrap_up_model`
   in settings; re-run the 2026-08-03 smoke test to confirm latency/cost move the way the
   pricing suggests.
4. If quality doesn't hold, at minimum re-evaluate `gpt-5.4-mini` vs Luna vs `gpt-5.4-pro`
   together — the roadmap item 1 comparison was never done and Luna adds a third option to it.

**Shipped:** all 4 steps completed. `gpt-5.6-luna` registered in `model_registry.py`;
`scripts/compare_outline_models.py` ran a head-to-head across 8 profiles (3 software-adjacent +
5 deliberately wider-spread: nurse, bakery owner, teacher, designer, financial analyst) — Luna
was 12–24x faster on every profile with no observed quality regression (full results and the
decision itself logged in `docs/architecture-decisions.md` §5, not duplicated here). Switched
`prompts/course-outline-proposal.md`'s `model:` field and `app/settings.py`'s `wrap_up_model`
default (which had silently drifted to `gpt-5.4-mini` since an unrelated commit 3 months ago —
`CLAUDE.md`/`.env.example` were stale and now corrected too) to `gpt-5.6-luna`. Verified: full
backend suite (248 passed), `make smoke` (11/11, after confirming an initial failure was a
pre-existing flake unrelated to this change — reproduced on the pre-switch tree too), and two
live end-to-end checks against the running stack — a real setup-outline generation and a real
end-session progress synthesis, both completing correctly on `gpt-5.6-luna` in seconds instead
of 1–2 minutes. `docs/qa-test-suite.md`'s course-outline-compile latency band tightened from
≤2min/≥5min to ≤10s/≥30s to match.
