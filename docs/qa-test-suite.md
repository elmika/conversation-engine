# QA Test Suite — Browser-Driven Learning Flow

Manual / AI-executable UI test scripts for the two flows that make up a learner's first
experience: **course setup** and **the first learning session**. Each is written as a
numbered script — one exact action per step, one exact expected result per step — so it can
be run identically by a human in a browser or by an AI agent driving Chrome
(`mcp__claude-in-chrome__*` tools). Neither requires reading application code to execute.

This complements, but doesn't replace, the other verification layers:
- `make test-backend` / `make test-frontend` — unit/integration tests, no network, no UI.
- `scripts/smoke_lesson_lifecycle.py` (`make smoke`) — scripted, API-level, asserts on
  `prompt_slug` and DB state directly. Fast, cheap-ish, no browser.
- **This document** — the only layer that actually renders the UI and reads it the way a
  learner would. Required by CLAUDE.md's End-to-End Verification Gate before any change to
  a user-facing flow is considered done.

---

## How to run

**Prerequisites:** `make up` running, a real `OPENAI_API_KEY` in `.env` (these tests make real
LLM calls — expect real cost and latency; see "Known flaky signals" below before failing a run
on speed).

**Fresh learner, every run:** these tests assume a brand-new learner (no existing profile). Get
a clean UUID by either:
- opening a fresh Incognito/Private window, or
- clearing `localStorage` for `localhost:3000`, or
- (AI agent) opening a new tab via `tabs_create_mcp` and navigating there — a new tab does not
  by itself guarantee a new UUID if `localStorage` is shared across tabs in the same profile;
  clear storage first if re-running in the same browser profile.

**Never navigate directly to a bare, unprefixed path** (`/history`, `/chat`, etc.) during these
tests — only follow links/buttons inside the app, or the root `/`. A bare-path navigation is a
known bug (see `docs/roadmap.md` item 2) that side-effects a new session; it will contaminate
the run.

**Recording:** capture a screenshot (or note manually) at every step marked 📸 below — these are
the points most likely to silently regress in a way plain text extraction won't catch (layout,
button presence/state, missing icon, etc.).

---

## Test 1 — Course Setup (new learner onboarding)

**Preconditions:** fresh learner (see above), `make up` stack healthy (`GET /healthz` → `200`).

| # | Action | Expected result |
|---|---|---|
| 1.1 | Navigate to `http://localhost:3000` | Auto-redirects to `/u/{uuid}/chat/{conversationId}`. No blank screen, no manual click needed to start. A new "Setup — Profile & Goal" conversation is already **Active** in the History sidebar. |
| 1.2 | Observe the first assistant message (no user input yet) | The **AI has already sent the first message** — the input is never blank waiting on the learner. Message is a short warm welcome + one-line explanation of what's about to happen, ending with a single question asking for the learner's **name**. 📸 |
| 1.3 | Reply with a free-text message that includes your name, role, and a stated learning goal (e.g. *"I'm Alex, a backend engineer, I want to learn pandas for data analysis"*) → Enter | Message sends (appears as a right-aligned bubble); a typing indicator appears; assistant reply addresses you **by name** and asks exactly **one** follow-up question, about your **industry**. No re-asking for your name. |
| 1.4 | Reply describing your industry | Assistant reply acknowledges it and asks **one** question about **why** you want this skill now / your motivation. |
| 1.5 | Reply describing your motivation | Assistant reply asks **one** question about your usual **session length** (e.g. "15 min / 30 min / an hour"). |
| 1.6 | Reply with a session length (e.g. "20-30 minutes") | Assistant proposes a **structured course outline**: a numbered list of modules (each with a bold title + one-sentence description), visibly tailored to the stated goal/industry (not generic). Ends with an instruction to click **"Let's start"** to begin. **This is the one step allowed to be slow** — up to ~2 minutes is fine, beyond ~5 minutes is a bug to flag regardless of cause — but the wait must be accompanied by a patience/progress UI element once `docs/roadmap.md` item 3 ships, not a bare typing indicator. 📸 |
| 1.7 | 📸 Inspect the header | A **"Let's start"** button (sparkle icon) is now present in the header, next to the prompt-slug selector. |
| 1.8 | Click **"Let's start"** | No error toast/banner. Within a few seconds, you are navigated into a **new** conversation, named after the proposed course, marked **Active** in History. The old "Setup — Profile & Goal" conversation remains in History but is **no longer Active**. |
| 1.9 | 📸 Inspect History sidebar | Exactly **2** conversations exist for this learner: the Setup conversation (inactive) and the new course conversation (active). No duplicates, no orphaned/empty conversations. |

**Pass criteria:** every step above matches; browser console has no errors (`read_console_messages`, `onlyErrors: true`); no HTTP 4xx/5xx in the network/API logs for this learner's requests except expected validation cases (none in this script); **latency requirement** — steps 1.2–1.5 (the framing Q&A) must each respond within **~3 seconds**, and **~5 seconds is already a fail**; step 1.6 (the course-outline compile) follows the separate 2 min / 5 min bands below instead.

---

## Test 2 — First Learning Experience (course session lifecycle)

**Preconditions:** Test 1 completed and passed; you are inside the newly created course
conversation; header shows the course name and an **"End Session"** button.

| # | Action | Expected result |
|---|---|---|
| 2.1 | Observe the opening message (no input yet) | Module list is rendered with the **current module marked** (e.g. `→`) and the rest previewed below it. Opening explanation is tied to the learner's stated goal/background from Test 1 (not generic). Message ends by **confirming the previously-stated session length** and asking if that still works today. 📸 |
| 2.2 | Reply confirming the session length (e.g. "Yes, that works") | Assistant responds with the first real teaching content for Module 1 — framed around your stated background (e.g. references that you already know Python) — and ends with a check-in question or a choice between two directions. |
| 2.3 | Reply picking one of the offered directions | Assistant response matches the direction you picked (not the other one), includes concrete content (e.g. a code example relevant to your stated goal/industry), and ends with a follow-up question or a small task. |
| 2.4 | Reply continuing the exchange (answer the question / attempt the task) | Assistant response is topically coherent with the prior three turns — no repeated questions, no lost context, no generic restart. |
| 2.5 | 📸 Inspect header | **"End Session"** button is present and clickable. |
| 2.6 | Click **"End Session"** | A **"Session complete"** card renders in place: full module list with the current module **checked off** (✓) and the next module marked as up next (`→`); a **"Where to pick up next time"** note that accurately summarizes the last topic actually covered (not boilerplate); **"Start next session"** and **"Close"** buttons both present. This must render within a reasonable time and never leave a bare spinner. 📸 |
| 2.7 | Click **"Close"** | Card dismisses. **No new conversation is created as a side effect** — this is a regression guard for the known `/history`-navigation bug (`docs/roadmap.md` item 2); explicitly check History count before/after this click. |
| 2.8 | 📸 Inspect History sidebar | Still exactly **2** conversations total (Setup + Course), same as end of Test 1. The course conversation is no longer marked Active. No duplicate "Course (2)"-style conversation appeared. |

**Pass criteria:** lesson content stays personalized and coherent at every turn; "End Session"
always produces a real summary (never hangs indefinitely, never errors); step 2.7 creates zero
new conversations — if it does, that's the `/history`-class bug recurring somewhere new and
should be filed, not waved off; **latency requirement** — every step in this test (2.1 through
2.6) must respond within **~3 seconds** (**~5 seconds is a fail**). Nothing in the
first-learning-experience flow gets the relaxed course-compile bands below — those are specific
to Test 1 step 1.6 only.

---

## Latency requirement

Two bands, depending on what the turn is doing:

| Turn type | Target | Fail threshold |
|---|---|---|
| Ordinary conversational turn (Test 1 steps 1.2–1.5; all of Test 2) | ≤ 3 seconds | ≥ 5 seconds |
| Course-outline compile (Test 1 step 1.6, only) | ≤ 2 minutes, **with** the patience/progress UI element from `docs/roadmap.md` item 3 | ≥ 5 minutes |

The course-outline compile is the one generation in the whole flow worth trading speed for
quality (see `docs/roadmap.md` item 1) — a 1–2 minute wait there is acceptable *only* if the
learner sees a dedicated "this may take a couple of minutes" treatment, not the bare chat typing
indicator, which reads as frozen well before the 2-minute mark. Every other step failing its
threshold is a bug to file, not noise to shrug off — 3 seconds is already a noticeably long
wait for a short conversational reply, and 5+ seconds is a clear regression regardless of model.

As of this writing, `user-profile-collection` (Test 1, steps 1.2–1.6) is not yet split by phase
and runs entirely on `gpt-5.4-pro`, so steps 1.2–1.5 currently take 45–140s each and will
legitimately **fail** the ordinary-turn threshold until `docs/roadmap.md` item 1 (the
framing-Q&A/course-outline phase split) ships. That's expected and intentional: this document
encodes the target behavior, not today's behavior — a failing run on steps 1.2–1.5 right now is
confirming the roadmap item is still open, not signaling a new regression.

---

## Other known flaky signals

- **Viewport-dependent click coordinates (AI-agent-specific):** if driving via Chrome tools,
  re-screenshot before every click rather than reusing coordinates from an earlier screenshot —
  the page viewport has been observed to resize between tool calls, which silently misdirects a
  click typed against stale coordinates. Prefer `find` (element ref) over raw coordinates where
  the tool supports it.

---

## Change log

| Date | Change |
|---|---|
| 2026-08-03 | Initial version, derived from the first live run of both tests. |
