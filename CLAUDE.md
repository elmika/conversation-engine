# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Local references

`.notes/` is gitignored and contains private architecture references for this project. Read it at the start of any session involving architecture decisions.

- `.notes/architecture.md` — vault paths for the layer model and templating architecture docs

## Project

**Conversation Engine** — A production-ready FastAPI + OpenAI service with streaming, conversation history, and hexagonal architecture.

**Prompt system:** Prompts are stored in SQLite, seeded from `prompts/*.md` on every startup (upsert — edits via admin UI are overwritten on restart if a matching file exists). See `docs/prompts.md` for full architecture, current DB state, and safe editing workflow.

**Section-file invariant:** Prompts may embed `{{course}}`, `{{user}}`, `{{progress}}` tags, which the resolver expands from `sections/<tag>/<user_id>.md`. A **missing** section file raises (surfaced as HTTP 400 / a `done` error event) — this strictness is deliberate, to catch misconfigured prompts. Therefore: any prompt that adds a section tag must guarantee that file exists for **all** learner states, especially the first session (a new learner has no `progress` file until a session ends). Setup completion seeds all three files for exactly this reason — see `app/learning/setup_completion.py`.

`sections/` itself is gitignored and only ever exists on the persistent volume, populated at runtime — never put a static, shared prompt template there. A file that's the same for every learner (a system prompt, even one used only for a background/end-of-session action) belongs in `prompts/`, seeded into the DB like every other prompt. Learned the hard way (2026-09-18): `sections/progress/progress-wrap-up.md` held the wrap-up instructions for post-session progress synthesis, but a fresh Fly volume never had it — `synthesise_progress()`'s best-effort error handling silently swallowed the resulting `FileNotFoundError`, and every learner's progress stayed frozen on its seeded placeholder forever. Fixed by moving it to `prompts/progress-wrap-up.md`.

## Commands

> **No local Python or Node.js required** — everything runs in Docker.

A `Makefile` wraps the most common tasks — run `make help` to list them. The raw Docker commands are documented below for cases that need more control (e.g. running a single test file).

**Start both services (hot-reload):**
```bash
make up
# API  → http://localhost:8000
# UI   → http://localhost:3000
```

Both `app/` and `prompts/` are volume-mounted and uvicorn runs with `--reload`, so backend changes take effect immediately without a rebuild. A rebuild (`make build`) is only needed when dependencies change (`requirements.txt`) or the Dockerfile itself changes.

**Backend tests:**
```bash
make test-backend
# or, for a single file/test:
docker build -t conversation-engine .
docker run --rm conversation-engine python -m pytest tests/test_chat.py          # single file
docker run --rm conversation-engine python -m pytest tests/test_chat.py::test_name  # single test
```

**Mocking after a refactor:** `unittest.mock.patch("module.function", ...)` binds at call time — it
patches the name in whichever module's namespace actually calls it, not the module that originally
imported/defined it. When logic is extracted into a helper (e.g. into `app/domain/` or `app/learning/`)
and the caller starts going through that helper instead of calling the function directly, existing
`patch("app.application.services.the_function", ...)` targets silently stop taking effect — repoint
them at the helper's own module. This surfaced when extracting `render_instructions()`: tests patching
`app.application.services.render_prompt` broke silently until repointed to
`app.domain.prompt_template.render_prompt`.

**Frontend tests:**
```bash
make test-frontend                                                                 # all tests
make test-watch                                                                    # watch mode
docker compose run --rm frontend pnpm test tests/lib/stream-parser.test.ts       # single file
```

**Add a frontend package:**
```bash
docker compose run --rm frontend pnpm add <package>
docker compose run --rm frontend pnpm add -D <package>
```

**Backend lint:**
```bash
make lint
make format
```

**CI:** `.github/workflows/ci.yml` (GitHub Actions) runs on every push. Backend: `ruff check`,
`ruff format --check`, pytest. Frontend: `tsc --noEmit`, Vitest, `next build`. It runs Python/Node
directly on the runner, not Docker, so keep its Python/Node versions and the ruff pin in sync with
the Dockerfiles. Run `make format` before pushing: unformatted code fails CI.

**Production build (both images):**
```bash
make build
```

**Check API keys first:** `make check-keys` (`scripts/check_api_keys.py`) verifies the
`OPENAI_API_KEY`/`ANTHROPIC_API_KEY` in `.env` against each provider's free `/v1/models`
endpoint and flags a running `api` container still holding an old key (`.env` edits need
`docker compose up -d api`). Run it before any live script below — the app reports a rejected
key only as a generic "502 Upstream … API error".

**Check for new models:** `make check-models` (`scripts/check_new_models.py`) diffs both
providers' live model lists against `model_registry.py`/`pricing.py` and reports NEW (released
in the last 180 days, not registered), UNPRICED and GONE (registered but retired) models. Neither
API exposes prices, so it prints the pricing pages to look them up by hand. Run it before any
model comparison — newer models keep shipping between tests.

**Compare candidate models:**
```bash
python3 scripts/compare_outline_models.py                                              # all profiles, default models
python3 scripts/compare_outline_models.py --models gpt-5.4-pro,gpt-5.6-luna --profiles nurse-research-statistics
```
Live head-to-head tool (needs `make up` + a real `OPENAI_API_KEY`, real cost) for deciding whether
to switch a prompt's pinned model. Drives the real flow against the running stack, varying only
`model_slug` on the turn under test, so the comparison sees exactly what a learner would — not a
re-implementation of the prompt/template logic. Used for the `gpt-5.6-luna` vs. `gpt-5.4-pro`
evaluation (`docs/architecture-decisions.md` §5); currently scoped to the setup/outline turn only.
Expected to be extended to other flow stages (lesson core/closure) and, once a second `LLMPort`
adapter exists, other providers — this will become routine as models keep shipping.

Every run is **recorded, not cached**: appended to `evals/results/<script>.jsonl` (committed —
these are the evidence behind `docs/model-decisions.md`, shareable as-is; see `evals/README.md`)
by `scripts/model_compare_results.py`. A (profile, model) cell already recorded under the same
prompt bodies and context models is shown from the log instead of re-run, so adding a model
only pays for the new cells. The key deliberately excludes the target prompt's own `model:` line
(the candidate overrides it) but includes the pinned models of the scenario's *other* prompts
(those turns run on their pins) — so switching a prompt's model doesn't throw away its own
comparison, while switching an upstream prompt correctly forces fresh runs. `--refresh` re-runs
and appends a newer record (never overwrites — e.g. to check a model hasn't drifted);
`--no-record` runs live without recording; `--label "Test N"` tags records to match the test
write-up. Any future per-tier comparison script (structured-extraction, guard tiers — see
`docs/model-decisions.md` "Claude as a second provider") should reuse `ResultsLog` rather than
re-inventing this.

```bash
python3 scripts/compare_session_models.py --target course-session-init --models claude-haiku-4-5,claude-sonnet-5-5
python3 scripts/compare_session_models.py --target course-session-core --models claude-sonnet-5-5
```
Chat-latency-tier counterpart, for `course-session-init/core/closure` and `user-profile-collection`
— the highest-traffic prompts (every session runs through them, not a one-time setup turn). These
four don't share one comparison shape, so `--target` picks a purpose-built scenario per prompt
(single opening turn, N canned mid-lesson turns, a forced time-over transition, etc. — see the
script's own docstring). Only the turn(s) matching `--target` get an explicit `model_slug`
override; every other turn in the scenario stays on its own currently-pinned model, so e.g.
comparing `course-session-core` doesn't also vary the objective-complete guard and confound the
result. Shares `scripts/session_test_utils.py` (admin-route SSE driving, throwaway section-file
provisioning, the `age_conversation`/`set_objective_met_db` DB shortcuts used to force phase
transitions deterministically — same technique as `make smoke`; `turn_models` reads which model
actually served each turn from the `runs` table, since SSE doesn't expose it) and the same
`ResultsLog`, in its own `evals/results/session_compare.jsonl`.

**Environment:** Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. Copy `frontend/.env.local.example` to `frontend/.env.local` (for local-only dev without Compose). Tests use `DATABASE_URL=sqlite:///:memory:` set in `tests/conftest.py`.

## End-to-End Verification Gate

A change to a user-facing flow is **not "done" and never "ready to merge" until the actual flow has been exercised against the running stack** (`make up` + the real path end-to-end), not just unit tests. Passing tests and a clean code review are necessary but **not sufficient** — green tests ≠ working flow.

- After finishing a feature or a review pass on a branch, smoke-test the real path (e.g. for the learning flow: new user → setup → outline → complete-setup → first course session → end-session → next session).
- For the **course-session lifecycle** (intro → core → closure, session-length capture/time-over), `make smoke` runs a scripted, self-checking live test against the running stack (`scripts/smoke_lesson_lifecycle.py`). It needs `make up` + a real `OPENAI_API_KEY` and makes real LLM calls. Use/extend it as the standing closing gate for that flow.
- `docs/qa-test-suite.md` is the browser-level counterpart to `make smoke` — numbered UI scripts (exact action → exact expected result) for course setup and the first learning session, runnable identically by a human or an AI agent driving Chrome. Use it as the concrete checklist when this gate calls for exercising the actual UI, and extend it whenever a new user-facing flow needs the same treatment.
- In your summary, state explicitly **what was exercised and what was not** (e.g. "API + BFF verified via curl; browser UI not clicked through").
- Do not describe a branch as "ready to merge." Report status and leave the merge decision to the user.
- `fly deploy` builds from the working tree, not git — deploying an uncommitted fix leaves prod running code that git history shows nothing about. Commit before (or immediately after) deploying, so the deployed state is always reproducible from `git log`.
- Fly apps that proxy or terminate a learner-facing SSE stream (e.g. the Next.js frontend) must have matching `auto_stop_machines`/`min_machines_running` settings to any backend they call end-to-end — an asymmetric setup (one app always-on, the other scaling to zero on idle) lets a cold start race an SSE connection and silently hang it with no error surfaced, easy to mistake for an app bug. Confirmed 2026-09-24: `skillforge-web`'s `min_machines_running=0` while `learning-platform`'s was `1` caused exactly this after a learner paused to read a course outline.

## Feature List Gate

`docs/features.md` is the canonical list of user-facing features, maintained for UX review.

**Updating `docs/features.md` is MANDATORY and must be the last step of every task that touches user-facing behaviour.** This includes new UI, changed interactions, new API behaviour surfaced in the UI, and removed functionality. Do not consider a task complete until the feature list has been updated.

## API Documentation Gate

`docs/openapi.yml` and `docs/postman_collection.json` are the source-of-truth API docs.

**Whenever you modify the backend API you must also update both files:**

| Change | openapi.yml | postman_collection.json |
|---|---|---|
| New route | Add `paths` entry + any new `components/schemas` | Add request item in correct folder |
| Removed route | Delete `paths` entry | Delete request item |
| Field renamed/retyped | Update schema `$ref` chain | Update example `body` |
| New query param | Add `parameters` entry | Add to `query` array |
| New error response | Add status code under `responses` | Add saved example response |
| New prompt slug | Update `/prompts` example | Update `/prompts` example response |

Rules:
- Use `$ref` for any schema referenced by more than one endpoint
- Every path must have at least one saved example response in the Postman collection
- SSE endpoints must describe all three event types (`meta`, `chunk`, `done`) in the `description` field
- The Postman test script on `POST /conversations` must keep the `conversation_id` variable assignment

## Frontend Architecture

Next.js 15 App Router frontend in `frontend/`. All API calls are proxied through BFF Route Handlers — the FastAPI URL is never exposed to the browser. See `docs/frontend.md` for full documentation.

```
frontend/
├── app/                   # Next.js App Router
│   ├── layout.tsx         # Root layout with QueryClientProvider
│   ├── page.tsx           # Redirect → /chat
│   ├── globals.css        # Tailwind + shadcn CSS variables
│   ├── providers.tsx      # QueryClientProvider
│   ├── chat/              # Chat interface pages
│   ├── history/           # Conversation browser
│   ├── admin/             # Prompt admin panel
│   └── api/               # BFF Route Handlers — proxy to FastAPI
│       ├── healthz/
│       ├── prompts/
│       ├── conversations/
│       └── conversations/[conversationId]/
├── components/
│   ├── ui/                # shadcn/ui primitives (button, input, select, …)
│   ├── chat/              # Chat-specific components
│   ├── history/           # History browser components
│   └── admin/             # Admin panel components
├── hooks/                 # TanStack Query + Zustand hooks
├── lib/
│   ├── utils.ts           # cn(), formatDate(), truncateId()
│   ├── types.ts           # TypeScript interfaces mirroring API schemas
│   ├── stream-parser.ts   # async generator: ReadableStream → typed SSE events
│   └── api-client.ts      # Typed fetch wrappers for BFF routes
└── tests/                 # Vitest + Testing Library + MSW
```

**Key decisions:**
- **BFF pattern**: Route Handlers read `FASTAPI_URL` server-side; clients use relative `/api/...` URLs
- **Streaming**: BFF pipes `upstream.body` (ReadableStream) directly — no manual chunking
- **State**: Zustand for UI state (active conversation, sidebar); TanStack Query for server state
- **shadcn/ui**: Components live in `components/ui/` as source — edit freely, not managed by CLI

**Mutation UX rule:** All user-triggered mutations (create, update, delete, enable, disable, rename…) must wait for the HTTP round-trip before updating the UI. Do **not** use optimistic updates. Instead, disable the triggering control and show a visible loading indicator (spinner or `isPending` prop) for the duration of the request. The UI updates only after the server confirms success. This prevents the confusion of controls that appear to do nothing, or records that disappear after a delay.

**Streaming scroll rule:** When auto-scrolling during token streaming, always use `behavior: "auto"` (instant jump), never `behavior: "smooth"`. Smooth animations restart on every chunk and actively fight user scroll gestures — the animation outruns the `scroll` event, so intent-detection fires too late. Use proactive intent detection (`wheel`/`touchmove`/`keydown`) rather than position-threshold detection, and re-engage following only when the user returns to the bottom. Once the current message grows taller than the visible area, stop auto-following for the rest of that message even if the reader hasn't scrolled — continuing to chase the tail otherwise yanks the text they're reading (the start of the message) out of view on every chunk. Reset this freeze for each new message so short replies still snap into view immediately.

**No dead ends rule:** Any error state a learner can reach during normal use (a 403 mid-session, an unrecognized URL, a failed mutation) must have a way back to a working screen — never just an error banner with no next step. When the recovery path is a redirect to another screen that already handles the situation (e.g. `/` re-showing the consent gate), suppress the raw error from ever rendering first; a screen that's about to navigate away shouldn't flash the technical failure message before it does.

## Backend Architecture

The app uses hexagonal (ports & adapters) architecture with four layers:

```
app/
├── main.py            # Entrypoint: wires infra, injects into app.state via lifespan
├── settings.py        # Pydantic-settings; reads .env
├── api/               # HTTP layer (FastAPI) — Layer API
│   ├── routes.py      # Thin routes: validate input, call service, format response/SSE
│   ├── schemas.py     # Request/response Pydantic models
│   └── middleware.py  # Adds request_id, logs endpoint + latency
├── application/       # Business logic (no infra imports)
│   ├── ports.py       # Interfaces: LLMPort, ConversationRepo, UnitOfWork, LearningFlowPort (Protocols) — Layer 1a
│   ├── use_cases.py   # Pure functions: chat(), stream_chat() — Layer 1a
│   └── services.py    # ConversationService: orchestrates history + LLM + persistence — Layer 1b
├── domain/            # Core, generic domain — Layer 1a (no learning-specific vocabulary)
│   ├── prompt_template.py  # {{tag}} rendering: file sections + {{time:*}} — render_instructions()
│   ├── model_registry.py   # Static registry of supported models (OpenAI + Anthropic), each tagged with a `provider`
│   ├── history.py     # trim_history(): caps context by turns/tokens before LLM calls
│   ├── entities.py    # Domain entities
│   └── value_objects.py    # ConversationId, PromptSlug
├── learning/           # Learning-platform logic — Layer 2 (see "Layer model" below)
│   ├── flow_orchestrator.py  # LearningFlowOrchestrator: the LearningFlowPort adapter
│   ├── setup_flow.py / lesson_flow.py   # phase → prompt-slug mapping (pure)
│   ├── objective_guard.py / session_length.py  # guard parsing, timing (pure)
│   ├── setup_completion.py   # "Let's start" → writes sections/{user,course}/<id>.md
│   ├── session_summary.py / progress_synthesis.py  # end-session summary + progress write
└── infra/             # Concrete adapters — Layer 1b
    ├── llm_openai.py  # OpenAILLMAdapter: wraps Responses API, handles retries/timeouts
    ├── llm_anthropic.py  # AnthropicLLMAdapter: wraps Messages API, same retry/timeout shape
    ├── llm_router.py  # RoutingLLMAdapter: dispatches to the right adapter by model_registry's `provider` field
    ├── slot_resolver_files.py  # FileSlotResolver: default SlotResolver, no Layer 2 knowledge
    ├── logging.py     # Structured JSON logging setup
    └── persistence/   # SQLite via sync SQLAlchemy
        ├── db.py      # Engine creation (StaticPool for tests)
        ├── models.py  # ORM: conversations, messages, runs tables
        └── repo_sqlalchemy.py  # ConversationRepo + UnitOfWork implementations
```

### Layer model

Three tiers, by product scale — full business-context version in the (gitignored, private)
`.notes/product-design.md`; this is the version every session and contributor sees regardless:

| Layer | What it is | Infra | Code |
|---|---|---|---|
| **L1** | Generic chat engine — reusable for any conversational product | FastAPI + LLM adapter | `app/api/`, `app/application/`, `app/domain/`, `app/infra/` |
| **L2** | Learning platform — lessons, setup, courses | Markdown section files | `app/learning/` |
| **L3** | School (not built) — teachers, curricula, cohorts | DB, multi-tenant | — |

L1 is split further, by **I/O purity, not genericity** — both halves are still generic, neither
knows what a "lesson" is:
- **L1a** — pure, no I/O: `app/domain/`, `app/application/ports.py`, `app/application/use_cases.py`.
- **L1b** — touches infra (DB, LLM calls) but is still generic: `app/application/services.py`, `app/infra/`.

**The rule:** a lower layer never imports from a higher one (L1a ⊂ L1b ⊂ L2 ⊂ API). Enforced by
`tests/test_architecture.py` (static import-graph check) + `make check-layers`, which also runs
automatically via a `PostToolUse` hook on every edit under `app/`.

**How L1b reaches L2 without importing it:** through a port, same pattern as `LLMPort`/`ConversationRepo`.
`LearningFlowPort` (`app/application/ports.py`, L1a) declares the seam; `LearningFlowOrchestrator`
(`app/learning/flow_orchestrator.py`, L2) implements it; `routes.py` wires the concrete adapter into
`ConversationService`'s constructor. `NullLearningFlow` (`ports.py`) is the trivial default — every
conversation is treated as a flat, phase-less prompt — proving `ConversationService` can run with
zero Layer 2 knowledge bound, the same guarantee `FileSlotResolver` gives `SlotResolver`. A future
L3 concept would follow this exact shape: a new port in `ports.py`, a concrete adapter above L2.

### Key design decisions

**Dependency injection via `app.state` + FastAPI `Depends`:** `main.py`'s `lifespan()` is the composition root for process-lifetime infra — it creates `Settings` and wires `app.state.llm` to a `RoutingLLMAdapter` (`OpenAILLMAdapter` + `AnthropicLLMAdapter`, dispatched by the model slug's `provider` in `model_registry.py`). Per-request dependencies (`uow_factory`, `PromptRepo`, `ConversationService`, `LearningFlowOrchestrator`) are built in `api/routes.py` via `Depends(...)` provider functions (`get_uow_factory`, `get_conversation_service`, etc.), since they need a request-scoped DB session. Nothing is constructed inside a use case.

**Ports (Protocols):** `LLMPort`, `ConversationRepo`, `UnitOfWork`, `SlotResolver`, and `LearningFlowPort` in `ports.py` are Python `Protocol` classes. The service layer depends only on these; the test suite injects fakes/mocks.

**ConversationService** (`application/services.py`) is the main orchestrator. It owns the transaction logic: for non-streaming, everything (persist user msg → call LLM → persist assistant msg + run) commits atomically. For streaming, setup commits immediately; the route calls `service.persist_stream_result()` after consuming the stream.

**History trimming:** Before each LLM call on existing conversations, `domain/history.py::trim_history()` caps history by `max_history_turns` and `max_history_tokens` (configured in `Settings`). This prevents context overflow and cost explosion.

**Sync SQLAlchemy with async HTTP:** The HTTP layer is async, but SQLAlchemy uses a sync engine. DB work runs in worker threads via `asyncio.to_thread()` in routes to avoid blocking the event loop.

**Never nest `uow_factory()`:** a `LearningFlowPort` method (or anything else that might run inside an already-open `ConversationService` transaction) must accept and reuse the caller's `uow` rather than opening a fresh one via `self._uow_factory()`. A second `BEGIN` on the same connection can deadlock — confirmed against the test suite's shared `StaticPool` connection (2026-09-17), where it silently hung the entire pytest run rather than failing fast.

**SQLite transactions must open `BEGIN IMMEDIATE`, not a plain deferred `BEGIN`:** any transaction that reads before it writes (the common case — e.g. `session.get()` then mutate) only takes a read lock at a deferred `BEGIN`; if another connection commits in between, this connection's later write-lock upgrade is a non-retryable `SQLITE_BUSY` — the busy handler is never invoked, no `busy_timeout` helps. Confirmed by reproducing it with raw `sqlite3` outside SQLAlchemy entirely (2026-09-29): 10 concurrent writers failed 9/10, instantly, regardless of `busy_timeout`. `app/infra/persistence/db.py`'s `_sqlite_explicit_begin` issues `BEGIN IMMEDIATE` for exactly this reason — don't revert it to `BEGIN` for a perceived read-concurrency win without re-reading that comment.

**Adding a new LLM provider:** implement `LLMPort` (see `OpenAILLMAdapter`/`AnthropicLLMAdapter` for the shape — retry loop, error mapping, `complete`/`stream`), tag every one of its models with `"provider": "<name>"` in `model_registry.py`, and register the adapter instance in `RoutingLLMAdapter`'s provider map (`app/infra/llm_router.py`, wired in `main.py`). Every call site keeps depending on a single `LLMPort` — the routing is invisible above `app.state.llm`. **Moving any prompt to a provider not already named on the consent screen is a consent change, not just a model change:** update the "Your messages are sent to …" sentence in `frontend/components/ConsentScreen.tsx` (and its description in `docs/features.md`) in the same change. It went stale silently on 2026-09-30 when `course-outline-proposal` moved to Claude, and was only caught by the browser QA run on 2026-10-29. Generating that sentence from the configured models (derived provider list, recorded per consent, 409 on a stale screen) was built and rejected on 2026-10-29 as overkill for a pilot with one hand-reviewed consent text — keep it a manual edit.

**Synchronous endpoints by default:** Backend endpoints must be synchronous by default — they complete their work and return the final result (200/201/204) before closing the connection. Async patterns (`BackgroundTasks`, task queues, `202 Accepted` with deferred processing) are only acceptable when there is an explicit use case that requires it (e.g. SSE streaming for LLM responses). Never introduce an async workflow speculatively or for performance reasons alone — the added complexity must be justified by a concrete requirement.

**SSE streaming shape:** Three event types — `meta` (conversation_id, model, slug), `chunk` (delta text), `done` (full message + timings, or `error` field on failure). Streaming routes always emit a terminal `done` event so clients never hang.

**Prompts:** stored in SQLite, seeded from `prompts/*.md` on startup (see "Prompt system" above) — there is no in-code prompt dict. The `default_prompt_slug` setting controls the fallback when a conversation has no prompt bound.

### Settings (key knobs)
| Setting | Default | Purpose |
|---|---|---|
| `default_model` | `gpt-4.1` | Model used for conversations |
| `wrap_up_model` | `gpt-5.6-luna` | Model used to synthesise progress at session end |
| `max_input_chars` | 32,000 | Input validation guard |
| `max_output_tokens` | 4,096 | Output cap |
| `request_timeout_s` | 60 | OpenAI call timeout |
| `max_retries` | 2 | Retry count with backoff |
| `max_history_turns` | 20 | History trim by turn count |
| `max_history_tokens` | 100,000 | History trim by token estimate |
| `database_url` | `sqlite:///./data/chat.db` | Persistence (override with env var) |

**FastAPI optional request body:** If an endpoint accepts a Pydantic body where all fields have defaults (callers may omit the body entirely), declare it as `body: MyModel = Body(default_factory=MyModel)`. Without this, FastAPI treats the body as required and returns a 422 when the client sends no body.
