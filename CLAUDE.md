# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Conversation Engine** — A production-ready FastAPI + OpenAI service with streaming, conversation history, and hexagonal architecture.

## Commands

**Local development:**
```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

**Tests (no API key needed — LLM is mocked):**
```bash
pytest
pytest -v
pytest tests/test_chat.py          # single test file
pytest tests/test_chat.py::test_name  # single test
```

**Lint:**
```bash
ruff check .
ruff format .
```

**Docker:**
```bash
docker build -t conversation-engine .
docker run --rm -p 8000:8000 --env-file .env conversation-engine
docker run --rm conversation-engine pytest -v
```

**Environment:** Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. Tests use `DATABASE_URL=sqlite:///:memory:` set in `tests/conftest.py`.

## Architecture

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
