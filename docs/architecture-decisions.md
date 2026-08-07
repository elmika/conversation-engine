# Architecture Decisions — Conversation Engine

> Backbone of the technical solution. Record of structural decisions and their rationale.
> Update this file when a significant architectural decision is made or revised.

---

## 1. LangChain / Langflow — when to adopt (deferred decision)

**Current decision:** Build manually with direct API calls. Do not adopt LangChain or Langflow yet.

**Rationale:** At PoC stage with individual prompts (profile collection, guard, course outline), a framework adds abstraction overhead without payoff. LangChain has known abstraction leakage — you fight it when your needs diverge from its assumptions. Hexagonal architecture + Protocol-based ports already give us the right boundaries.

**Switch triggers — revisit when any of these apply:**

1. **RAG over course content** — indexing learning material and retrieving relevant chunks per student or topic. LangChain's RAG tooling is mature and saves significant work here.
2. **Complex multi-step agent pipelines** — 4+ chained LLM calls with conditional branching (profile → gap analysis → curriculum → lesson → assessment → feedback loop). Manual orchestration gets messy at that scale.
3. **Session memory management** — structured persistence and retrieval of conversation history across sessions beyond what direct API calls handle cleanly.

**Langflow specifically:** Use as a *design tool only* — prototype complex flows visually, then implement directly in code. Not production infrastructure.

**LangSmith:** Add early regardless — lightweight tracing and observability from day one, independent of whether LangChain is ever adopted.

*Added: 2026-05-11*

---

## 2. Auth — learner vs. admin, two different mechanisms

**Learner identity:** already solved, no change needed. `crypto.randomUUID()` generated client-side on first visit, persisted in `localStorage`, carried in every `/u/{userId}/...` URL. No login. Since there's no email/password recovery, the UUID *is* the account — if a learner loses it (clears storage, switches device, never bookmarks), their course and progress are unreachable. **Product implication, not just technical:** the UI must explicitly instruct the learner to bookmark their `/u/{userId}/...` home page once their course outline is created — that bookmark is the only recovery path. This is a session-close / onboarding UX requirement, not an auth feature to build.

**Admin gating:** static bearer token(s) via env var, checked by a FastAPI dependency on the admin router (`secrets.compare_digest`, not `==`). One token per role (superadmin / tenant admin) mapping to a role string in that dependency — keeps routes/URLs identical across both roles per the API-transparency requirement, and is a one-file change if a second real tenant admin ever exists. No sessions, no DB, no login UI.

**Why two different mechanisms and not one:** the learner side optimizes for zero-friction entry (no signup wall for a demo audience); the admin side optimizes for restricting spend visibility and other learners' conversations to the operator only. Conflating them (e.g. forcing admin through the same UUID scheme) would either weaken admin protection or add friction learners don't need.

**Not addressed by either:** this gates *access* to `/admin` and gives learners a private space, but does nothing to cap spend if the learner-facing UUID scheme is discovered/scraped/looped by something other than a human learner. Usage/cost visibility and ceilings/enforcement are a separate, still-open piece.

*Added: 2026-08-05*

---

## 3. Lesson prompt architecture

**Principle: code infers what code can; prompts judge only what code cannot.** Deterministic state must never be a model inference — it is more reliable, testable, faster and cheaper in code. State that genuinely needs judgment gets its own single-purpose prompt that does *nothing else* — no teaching or content instructions mixed in. Mixing state-inference with content is what made the "intro twice" and "jumping to next session" bugs invisible and untestable.

**State taxonomy for a lesson:**

| State | Owner | How |
|---|---|---|
| Is this the opening turn? | Code | Empty conversation history |
| Is the session time over? | Code | Elapsed vs. session length from profile |
| Has the lesson objective been reached? | Prompt (guard) | Cheap-model binary/structured judgment, fired at decision points |

**A lesson has three moments, each its own prompt:**

1. **Introduction** — course material (module list) + initial question. Fires at session open.
2. **Core** — the teaching/coaching loop. No state-transition language.
3. **Closure** — wrap-up + what's next.

Code orchestrates the transitions using the deterministic flags above plus the objective guard.

**Shipped** (bites 3a–3d): `course-session-init.md` decomposed into `course-session-init` (Introduction), `course-session-core` (Core — replaces the originally-planned `teaching` prompt name), `course-session-closure` (Closure — replaces the originally-planned `progress-synthesis` prompt name), plus the `lesson-objective-complete` guard (`app/learning/objective_guard.py`) and `session-length-extraction` (captures an in-chat "adjust today's length" override). Closure fires on EITHER trigger: code-owned time-over, or the objective guard latching `objective_met`.

*Added: 2026-06-24 (decision); build status confirmed 2026-08-07*

---

## 4. Testing strategy — prompts & state

The lesson architecture (§3) splits the testing problem into two layers. The whole point of moving state into code is that most of what used to be untestable prompt behaviour collapses into Layer A — the cheap, deterministic layer.

**Layer A — deterministic logic (plain pytest, runs in CI on every commit).** Turn position (opening turn?), time-over flag, and the orchestration itself — "given state X, which prompt fires next?" No LLM calls. Shipped: unit tests on `session_length.py` and `objective_guard.py`.

**Layer B — prompt behaviour (needs an LLM, so NOT on every commit).** The objective guard returns a clean yes/no on fixed transcripts; the intro renders the module list exactly once; the core prompt never re-emits the intro format. Two sub-options:
- **B(i) recorded/golden tests** — capture real responses through the `LLMPort` adapter, replay in CI. Deterministic and free, but goes stale. **Not started.**
- **B(ii) live smoke harness** — real calls, run on demand. Catches model drift; assert on *shape*, not exact text. **Shipped**: `scripts/smoke_lesson_lifecycle.py` / `make smoke`, 11/11 against the objective path.

**Tooling: no LangChain/LlamaIndex for orchestration.** The lesson flow is a deterministic 3-state machine (intro → core → closure) with one binary guard — `if`/`elif`, not a framework. This is the same framework-adoption question as **§1** (LangChain/Langflow — when to adopt); §1's switch triggers haven't fired for this piece either. Prompt management/testing stays a test-time concern (pytest + `LLMPort` mock/record), never a runtime dependency — add Promptfoo only if eval matrices (many transcripts × many prompt versions, scored) are later needed.

*Added: 2026-06-24 (decision); build status confirmed 2026-08-07*

---

*Created: 2026-04-21*
