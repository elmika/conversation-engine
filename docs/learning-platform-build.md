# Learning Platform — Current Build

> As-built state of the learning-platform features on top of the conversation engine, current.
> See `docs/architecture-decisions.md` §3–4 for the decisions this build implements, and
> `docs/build-status.md` for prompt-by-prompt build status.

---

## Session model

Every session — setup or course — follows the same structure:

```
Session start   → AI opens immediately, no blank input
Ongoing session → one or more sub-sessions executed sequentially
Session end     → summary + next step + close button
```

### Setup flow — current implementation (as built)

**Status: live.** Two driving prompts run the interview in sequence — `user-profile-collection` (4 framing questions: name, role/industry, motivation, session length) then `course-outline-proposal` (synthesizes the tailored outline) — split for cost (the outline call alone is worth frontier-tier pricing; the framing questions aren't). Ends by inviting the learner to click **Let's start**.

Completion is **explicit and user-triggered**, not guard-detected:

```
New learner (no sections/user/<id>.md)
  → AI opens the setup conversation (user-profile-collection → course-outline-proposal)
  → 4 framing questions, then tailored outline, in one conversation
  → learner clicks "Let's start"   (POST /u/{id}/conversations/{cid}/complete-setup)
       → user-profile-extraction    → sections/user/<id>.md
       → course-outline-extraction  → sections/course/<id>.md   (synchronous)
       → setup conversation ended (LAST, so a failure leaves it resumable)
  → first course session opens (course-session-init)
```

Why simpler: no orchestration engine to build, and the learner keeps explicit control over when setup ends. Extraction runs synchronously on confirm (the learner is actively waiting on it) and is ordered + atomic so a failure never leaves a half-written profile.

### Sub-sessions (deferred, not built)

An ongoing session composed of **sub-sessions** — focused units with a defined objective, executed transparently in a single conversation, boundaries invisible to the user. Each sub-session has: `objective`, `completion_criteria` (checklist for a guard prompt), `min_turns`, `guard_model` (cheapest/fastest — binary judgment only), `async_action` (what fires on completion).

**Guard mechanism (not built for setup):** after `min_turns`, fire a separate cheap LLM call with a yes/no prompt, e.g. "The user profile is complete when we have: name, role, technology background. Have all three been established? Answer only: yes or no." On "yes": async action fires silently, conversation transitions naturally.

**Note:** the *separation principle* this implies (single-purpose state prompts; code owns deterministic state) **is already adopted for the lesson flow** — see `docs/architecture-decisions.md` §3. What's still deferred here is orchestration *depth*: automatically chaining multiple sub-sessions within setup. Session-level endings (end button, confirm button) stay UI-triggered regardless; the guard would only handle mid-session transitions.

**Adopt when** any of: (a) setup needs more than the current one-conversation interview; (b) course sessions need automatic explanation→exercise→feedback transitions beyond the current init/core/closure split.

---

## User and course model

Users and courses are identified by **slug**. Sections files are keyed by slug:

```
sections/
  user/<slug>.md        ← learner profile
  course/<slug>.md      ← personalised course outline
  progress/<slug>.md    ← learner progress snapshot
```

At setup end: `user/<slug>.md` and `course/<slug>.md` are written.
At session end: `progress/<slug>.md` is updated by `course-session-closure`.
The active slug is passed at conversation start — currently via env var, needs to be runtime-selectable.

**User slug:** generated from name at onboarding (e.g. "Alex" → `alex`). In practice the real identity mechanism is the anonymous UUID in `/u/{userId}/...` (see `docs/architecture-decisions.md` §2) — the slug is the profile filename, not a separate identity system.

**No login for learners** — see §2 for why that's a deliberate choice, not a gap.

---

## General principles (non-negotiable)

- AI always opens — no blank input ever
- One thing at a time — no multi-part prompts or dumps
- Close is always available — no gates
- Background processing never blocks the user
- Name what happened, name what's next — no generic "session complete"
