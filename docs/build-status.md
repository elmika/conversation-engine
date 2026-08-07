# Build Status — Conversation Engine (Technical)

> Technical feature inventory for the backend/frontend/prompts. Not a roadmap (see `docs/roadmap.md`)
> and not an API contract (see `docs/openapi.yml`) — this is "what's actually built."

---

## Legend

| Status | Meaning |
|---|---|
| `done` | Built and working |
| `partial` | Started but incomplete |
| `designed` | Design defined, not yet built |
| `idea` | Surfaced but not yet designed |

---

## Backend (FastAPI)

| Feature | Status | Notes |
|---|---|---|
| Multi-turn conversation engine | `done` | |
| SSE streaming | `done` | |
| Conversations CRUD | `done` | 20+ HTTP endpoints |
| Rewind (undo last turn) | `done` | |
| End session endpoint | `done` | Triggers progress synthesis |
| Session wrap-up — LLM progress synthesis | `done` | Called on end-session |
| History trimming | `done` | By turns (20) and tokens (100k) |
| Prompt persona system (slug-based) | `done` | Supports `{{course}}`, `{{user}}`, `{{progress}}`, `{{time:*}}` variables |
| Sections system (file-based content injection at render time) | `done` | user, course, progress sections |
| Prompt CRUD | `done` | |
| `user-profile-collection` (setup, framing only) | `done` | Narrowed to 4 framing questions on `gpt-4.1`; outline turn split out below (cost — see `docs/roadmap.md`) |
| `course-outline-proposal` (setup, outline) | `done` | Split out onto `gpt-5.4-pro` — the one setup call judged worth frontier-tier cost |
| `course-session-init` / `course-session-core` / `course-session-closure` | `done` | Lesson decomposed into Introduction/Core/Closure moments per `docs/architecture-decisions.md` §3 (bites 3a–3d) |
| `session-length-extraction` | `done` | Captures an in-chat "adjust today's length" override, consumed by the code-owned time-over check |
| `lesson-objective-complete` guard | `done` | `app/learning/objective_guard.py`; latches `objective_met`; closure fires on this OR time-over |
| Model registry | `done` | 14 OpenAI models; per-prompt model override |
| Claude API integration | `partial` | Built on `add-claude` branch — needs validation + merge |
| SQLite persistence via SQLAlchemy | `done` | Sync, offloaded to thread |
| `usage` / `finish_reason` extraction | `partial` | DB columns exist in ORM; `OpenAILLMAdapter` doesn't populate them |
| Structured logging + middleware | `done` | |
| Composition root (no hidden DI) | `done` | `main.py` |
| Hexagonal architecture (ports as Python Protocol classes) | `done` | Domain layer has zero infra imports |

---

## Frontend (Next.js 15, App Router)

| Feature | Status | Notes |
|---|---|---|
| Chat interface (streaming) | `done` | |
| Rewind button | `done` | |
| Model selector | `done` | |
| Prompt selector | `done` | |
| End session button | `done` | |
| Conversation history list (paginated) | `done` | |
| Admin panel — prompt CRUD | `done` | |
| BFF pattern (route handlers proxy to FastAPI) | `done` | Frontend uses relative `/api/...` |
| Problem anchor — pinned pane above conversation | `designed` | Always visible; scenario, current step, progress bar |
| Notebook side pane | `designed` | Always-open alongside conversation; capture as-you-go or at close |

---

## Data model

| Feature | Status | Notes |
|---|---|---|
| Conversation + message persistence | `done` | SQLite |
| Timestamped progress archive | `done` | e.g. `sections/progress/20260330T152746Z.md` |
| Per-user course instance | `idea` | Two-layer model: reusable course skeleton + personalized instance |
| Auth / multi-user session isolation | `idea` | Defer until learning experience validated |

---

## Test coverage

| Feature | Status | Notes |
|---|---|---|
| 15 test files, in-memory SQLite, LLM mocked | `done` | Run via `make test-backend` |
| Progress update e2e test | `partial` | Logic built and dogfooded; not formally validated |

---

## Branches / pending work

| Branch | Status | Contents |
|---|---|---|
| `learning-lifecycle` | 0 commits ahead of `main` — superseded, safe to delete | Lesson complete lifecycle, progress update logic, control model |
| `add-claude` | open, 2 commits ahead | Claude provider + model registry additions |
| `prompts` | open, 1 commit ahead | TypeScript module 3 content |

---

*Last updated: 2026-08-07. Repo: `elmika/conversation-engine`, branch `main`.*
