# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Local references

`.notes/` is gitignored and contains private architecture references for this project. Read it at the start of any session involving architecture decisions.

- `.notes/architecture.md` — vault paths for the layer model and templating architecture docs

## Project

**Conversation Engine** — A production-ready FastAPI + OpenAI service with streaming, conversation history, and hexagonal architecture.

**Prompt system:** Prompts are stored in SQLite, seeded from `prompts/*.md` on every startup (upsert — edits via admin UI are overwritten on restart if a matching file exists). See `docs/prompts.md` for full architecture, current DB state, and safe editing workflow.

**Section-file invariant:** Prompts may embed `{{course}}`, `{{user}}`, `{{progress}}` tags, which the resolver expands from `sections/<tag>/<user_id>.md`. A **missing** section file raises (surfaced as HTTP 400 / a `done` error event) — this strictness is deliberate, to catch misconfigured prompts. Therefore: any prompt that adds a section tag must guarantee that file exists for **all** learner states, especially the first session (a new learner has no `progress` file until a session ends). Setup completion seeds all three files for exactly this reason — see `app/learning/setup_completion.py`.

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

**Production build (both images):**
```bash
make build
```

**Environment:** Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. Copy `frontend/.env.local.example` to `frontend/.env.local` (for local-only dev without Compose). Tests use `DATABASE_URL=sqlite:///:memory:` set in `tests/conftest.py`.

## End-to-End Verification Gate

A change to a user-facing flow is **not "done" and never "ready to merge" until the actual flow has been exercised against the running stack** (`make up` + the real path end-to-end), not just unit tests. Passing tests and a clean code review are necessary but **not sufficient** — green tests ≠ working flow.

- After finishing a feature or a review pass on a branch, smoke-test the real path (e.g. for the learning flow: new user → setup → outline → complete-setup → first course session → end-session → next session).
- In your summary, state explicitly **what was exercised and what was not** (e.g. "API + BFF verified via curl; browser UI not clicked through").
- Do not describe a branch as "ready to merge." Report status and leave the merge decision to the user.

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

## Backend Architecture

The app uses hexagonal (ports & adapters) architecture with four layers:

```
app/
├── main.py            # Entrypoint: wires infra, injects into app.state via lifespan
├── settings.py        # Pydantic-settings; reads .env
├── api/               # HTTP layer (FastAPI)
│   ├── routes.py      # Thin routes: validate input, call service, format response/SSE
│   ├── schemas.py     # Request/response Pydantic models
│   └── middleware.py  # Adds request_id, logs endpoint + latency
├── application/       # Business logic (no infra imports)
│   ├── ports.py       # Interfaces: LLMPort, ConversationRepo, UnitOfWork (Protocols)
│   ├── use_cases.py   # Pure functions: chat(), stream_chat()
│   └── services.py    # ConversationService: orchestrates history + LLM + persistence
├── domain/            # Core domain
│   ├── prompt_registry.py  # PROMPTS dict keyed by slug; get_prompt(), validate_prompt_slug()
│   ├── history.py     # trim_history(): caps context by turns/tokens before LLM calls
│   ├── entities.py    # Domain entities
│   └── value_objects.py    # ConversationId, PromptSlug
└── infra/             # Concrete adapters
    ├── llm_openai.py  # OpenAILLMAdapter: wraps Responses API, handles retries/timeouts
    ├── logging.py     # Structured JSON logging setup
    └── persistence/   # SQLite via sync SQLAlchemy
        ├── db.py      # Engine creation (StaticPool for tests)
        ├── models.py  # ORM: conversations, messages, runs tables
        └── repo_sqlalchemy.py  # ConversationRepo + UnitOfWork implementations
```

### Key design decisions

**Dependency injection via `app.state`:** `main.py` is the single composition root. It creates `Settings`, `OpenAILLMAdapter`, and a `uow_factory`, then stores them on `app.state`. Routes read from `app.state` — nothing is constructed in routes or use cases.

**Ports (Protocols):** `LLMPort`, `ConversationRepo`, and `UnitOfWork` in `ports.py` are Python `Protocol` classes. The service layer depends only on these; the test suite injects fakes/mocks.

**ConversationService** (`application/services.py`) is the main orchestrator. It owns the transaction logic: for non-streaming, everything (persist user msg → call LLM → persist assistant msg + run) commits atomically. For streaming, setup commits immediately; the route calls `service.persist_stream_result()` after consuming the stream.

**History trimming:** Before each LLM call on existing conversations, `domain/history.py::trim_history()` caps history by `max_history_turns` and `max_history_tokens` (configured in `Settings`). This prevents context overflow and cost explosion.

**Sync SQLAlchemy with async HTTP:** The HTTP layer is async, but SQLAlchemy uses a sync engine. DB work runs in worker threads via `asyncio.to_thread()` in routes to avoid blocking the event loop.

**Synchronous endpoints by default:** Backend endpoints must be synchronous by default — they complete their work and return the final result (200/201/204) before closing the connection. Async patterns (`BackgroundTasks`, task queues, `202 Accepted` with deferred processing) are only acceptable when there is an explicit use case that requires it (e.g. SSE streaming for LLM responses). Never introduce an async workflow speculatively or for performance reasons alone — the added complexity must be justified by a concrete requirement.

**SSE streaming shape:** Three event types — `meta` (conversation_id, model, slug), `chunk` (delta text), `done` (full message + timings, or `error` field on failure). Streaming routes always emit a terminal `done` event so clients never hang.

**Prompt registry:** Prompts live in `domain/prompt_registry.py` as a dict. To add a new persona, add an entry to `PROMPTS` with a slug key and a `system_prompt`. The `default_prompt_slug` setting controls the fallback.

### Settings (key knobs)
| Setting | Default | Purpose |
|---|---|---|
| `default_model` | `gpt-4.1` | Model used for conversations |
| `wrap_up_model` | `gpt-5.4-pro` | Model used to synthesise progress at session end |
| `max_input_chars` | 32,000 | Input validation guard |
| `max_output_tokens` | 4,096 | Output cap |
| `request_timeout_s` | 60 | OpenAI call timeout |
| `max_retries` | 2 | Retry count with backoff |
| `max_history_turns` | 20 | History trim by turn count |
| `max_history_tokens` | 100,000 | History trim by token estimate |
| `database_url` | `sqlite:///./data/chat.db` | Persistence (override with env var) |
