# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Conversation Engine** — A production-ready FastAPI + OpenAI service with streaming, conversation history, and hexagonal architecture.

## Commands

> **No local Python or Node.js required** — everything runs in Docker.

**Start both services (hot-reload):**
```bash
docker compose up
# API  → http://localhost:8000
# UI   → http://localhost:3000
```

**Backend tests:**
```bash
docker build -t conversation-engine .
docker run --rm conversation-engine python -m pytest -v
docker run --rm conversation-engine python -m pytest tests/test_chat.py          # single file
docker run --rm conversation-engine python -m pytest tests/test_chat.py::test_name  # single test
```

**Frontend tests:**
```bash
docker compose run --rm frontend pnpm test                                        # all tests
docker compose run --rm frontend pnpm test tests/lib/stream-parser.test.ts       # single file
docker compose run --rm frontend pnpm test:watch                                  # watch mode
```

**Add a frontend package:**
```bash
docker compose run --rm frontend pnpm add <package>
docker compose run --rm frontend pnpm add -D <package>
```

**Backend lint:**
```bash
docker run --rm conversation-engine python -m ruff check .
docker run --rm conversation-engine python -m ruff format .
```

**Production build (both images):**
```bash
docker build -t conversation-engine .
docker build -t conversation-engine-frontend ./frontend
```

**Environment:** Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. Copy `frontend/.env.local.example` to `frontend/.env.local` (for local-only dev without Compose). Tests use `DATABASE_URL=sqlite:///:memory:` set in `tests/conftest.py`.

## Feature List Gate

`docs/features.md` is the canonical list of user-facing features, maintained for UX review.

**Whenever you add, change, or remove a user-facing feature, update `docs/features.md`** to reflect it — add new entries, update descriptions, or remove entries as appropriate. This applies to anything a user can see or interact with: new UI, new API behaviour exposed in the UI, changed workflows, or removed functionality.

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

**SSE streaming shape:** Three event types — `meta` (conversation_id, model, slug), `chunk` (delta text), `done` (full message + timings, or `error` field on failure). Streaming routes always emit a terminal `done` event so clients never hang.

**Prompt registry:** Prompts live in `domain/prompt_registry.py` as a dict. To add a new persona, add an entry to `PROMPTS` with a slug key and a `system_prompt`. The `default_prompt_slug` setting controls the fallback.

### Settings (key knobs)
| Setting | Default | Purpose |
|---|---|---|
| `openai_model` | `gpt-4.1-mini` | OpenAI model |
| `max_input_chars` | 32,000 | Input validation guard |
| `max_output_tokens` | 4,096 | Output cap |
| `request_timeout_s` | 60 | OpenAI call timeout |
| `max_retries` | 2 | Retry count with backoff |
| `max_history_turns` | 20 | History trim by turn count |
| `max_history_tokens` | 100,000 | History trim by token estimate |
| `database_url` | `sqlite:///./data/chat.db` | Persistence (override with env var) |
