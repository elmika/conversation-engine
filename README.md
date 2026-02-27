# Conversation Engine

Production-ready conversation engine built with FastAPI and OpenAI. Features dynamic prompts, streaming responses, conversation history management, and clean hexagonal architecture. Designed for flexibility, quality control, and maintainability.

## Setup (OpenAI API key)

To call the real conversation endpoints, the app needs an OpenAI API key. Tests use a mocked LLM and do **not** require a key.

1. Copy the example env file and add your key:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```
   Create or manage keys at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

2. When running with Docker, the container must receive this variable. Use either:
   - **`--env-file .env`** (recommended): passes all variables from `.env` into the container.
   - **`-e OPENAI_API_KEY=sk-...`**: pass the key explicitly.

## Run and test with Docker (no local install)

From the repo root. The image runs as a non-root user and uses a multi-stage build.

**Build the image** (default: includes app + tests)

```bash
docker build -t conversation-engine .
```

Optional: build a slimmer production-only image (no pytest):

```bash
docker build --target prod -t conversation-engine:prod .
```

**Run the app** (with API key so conversation endpoints work)

```bash
docker run --rm -p 8000:8000 --env-file .env conversation-engine
```

If you prefer not to use a file: `docker run --rm -p 8000:8000 -e OPENAI_API_KEY=sk-your-key conversation-engine`.

- Health: http://127.0.0.1:8000/healthz  
- API docs: http://127.0.0.1:8000/docs  

**Run tests** (no API key needed; use default image, not `conversation-engine:prod`)

```bash
docker run --rm conversation-engine pytest -v
```

Test gate: fix any failing tests before considering a change complete.

## Run locally (optional)

If you have Python and pip:

```bash
cp .env.example .env   # then set OPENAI_API_KEY in .env
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Tests: `pytest` or `pytest -v`.

## Light load testing & TTFB

These examples assume the app is running on `http://127.0.0.1:8000` (locally or via Docker).

- **Single streaming request (measure client-side TTFB and total time)**  
  ```bash
  curl -w 'TTFB=%{time_starttransfer}s TOTAL=%{time_total}s\n' \
    -N -X POST http://127.0.0.1:8000/conversations/stream \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"Say hello briefly."}]}'
  ```  
  This shows wall-clock TTFB and total duration from the client’s perspective; compare it with the `timings` we return in the final `done` event.

- **Light load on non-streaming endpoint (example with `hey`)**  
  ```bash
  hey -n 50 -c 5 -m POST \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"Hello"}]}' \
    http://127.0.0.1:8000/conversations
  ```  
  This issues 50 requests with up to 5 in flight; use the reported p50/p90 latencies alongside the `timings` fields in responses to get a feel for behaviour under small concurrent load.

- **Light load without extra tools (Python snippet)**  
  ```bash
  python - << 'EOF'
  import asyncio
  import time

  import httpx

  URL = "http://127.0.0.1:8000/conversations"
  PAYLOAD = {"messages": [{"role": "user", "content": "Ping"}]}

  async def one_call(client: httpx.AsyncClient) -> float:
      start = time.perf_counter()
      r = await client.post(URL, json=PAYLOAD)
      r.raise_for_status()
      return (time.perf_counter() - start) * 1000

  async def main() -> None:
      async with httpx.AsyncClient(timeout=10.0) as client:
          tasks = [one_call(client) for _ in range(20)]
          latencies = await asyncio.gather(*tasks)
      latencies_rounded = [round(x) for x in latencies]
      print("latencies_ms:", latencies_rounded)
      print("avg_ms:", round(sum(latencies) / len(latencies)))

  asyncio.run(main())
  EOF
  ```  
  This sends a small burst of requests and prints per-call and average latency; for deeper analysis, you can also inspect each response’s `timings` field.

## Architecture overview

- **Entry point**: `app/main.py` creates the FastAPI app, sets up logging and the SQLite engine in a lifespan hook, creates a single `Settings` instance and OpenAI adapter, and stores them on `app.state` so the rest of the app can reuse them.
- **API layer**: `app/api/routes.py` defines HTTP endpoints and uses `app/api/schemas.py` for request/response models. `app/api/middleware.py` adds a `request_id` to each request and logs endpoint, status code, and latency.
- **Application layer**: `app/application/use_cases.py` contains the “chat” and “stream_chat” use cases; `app/application/ports.py` defines the `LLMPort` and `ConversationRepo` interfaces so routes and use cases depend on abstractions, not concrete infra.
- **Domain layer**: `app/domain/prompt_registry.py` holds prompt specs keyed by `prompt_slug` (e.g. default vs. conflict-coach prompts).
- **Infra layer**: `app/infra/llm_openai.py` wraps the OpenAI Responses API; `app/infra/persistence/db.py`, `models.py`, and `repo_sqlalchemy.py` implement SQLite persistence for conversations, messages, and runs; `app/infra/logging.py` sets up structured logging.

**Request flow (non-streaming)**:
- **1.** Client calls `POST /conversations` (first turn) or `POST /conversations/{conversation_id}` (append) with new messages (and optional `prompt_slug`).
- **2.** Route validates the body, enforces `max_input_chars`, and asks the `ConversationRepo` to persist the new user messages.
- **3.** For appends, the use case is invoked with the full conversation history (`get_messages(...)` + new messages) so the LLM sees previous user and assistant turns as context; for first turns, only the new messages are sent.
- **4.** The OpenAI adapter calls the Responses API with timeout, output cap, and retry; the use case returns assistant text + timings.
- **5.** Route persists the assistant message and run metadata, then returns a `ConversationResponse` envelope.

**Request flow (streaming)**:
- **1.** Client calls `POST /conversations/stream` or `POST /conversations/{conversation_id}/stream`.
- **2.** Route validates input, persists user messages, and calls the `stream_chat` use case with `LLMPort.stream` in a worker thread so the event loop stays responsive.
- **3.** As the OpenAI adapter yields `StreamEvent` items, the route converts them into SSE events (`meta`, `chunk`, `done`) and streams them back to the client.
- **4.** When the stream finishes, the final assistant message and run metadata are persisted in the background.

## Design choices & rationale

- **Hexagonal-ish structure**: Keep HTTP concerns in `api/`, business logic in `application/`, prompts in `domain/`, and infrastructure details in `infra/`, so it’s easy to swap out infra (LLM provider, database) without rewriting the core flows.
- **Ports and adapters, wired from `main`**: Routes and use cases depend on `LLMPort` and `ConversationRepo` interfaces; `app/main.py` is the single place that decides “use OpenAI + SQLite” and injects concrete adapters via `app.state`, which simplifies testing and future changes.
- **Sync SQLAlchemy with thread offload**: The app is async at the HTTP layer but uses the sync SQLAlchemy engine; DB work is done in worker threads (`asyncio.to_thread`) to avoid blocking the event loop while keeping the persistence layer simple.
- **OpenAI Responses adapter**: A thin wrapper around the Responses API that normalizes both non-streaming and streaming calls into typed results (`LLMResult`, `StreamEvent`), and centralizes timeouts, max output tokens, basic retry with backoff, and response parsing.
- **Error handling and observability**: A middleware assigns `request_id` and logs endpoint, status, and latency; a global exception handler logs unhandled errors (including `request_id`) and returns a consistent 500 envelope, while streaming paths are designed to evolve toward structured SSE error events.
- **Persistence and analytics hooks**: Conversations, messages, and runs are stored in SQLite for local/demo use; the `runs` table tracks timing now and is ready to record token counts and finish reasons once they’re wired from the OpenAI responses.
- **Containerization**: The Dockerfile uses a multi-stage build; the default image includes dev tools so you can both run the app and `pytest`, and there’s an optional slimmer `prod` target. Containers run as a non-root user with a writable `/app/data` directory for SQLite.

## More

- **[API.md](API.md)** — Example requests, response shapes, and quick command-line tests for all endpoints.
- **[RISKS-AND-IMPROVEMENTS.md](RISKS-AND-IMPROVEMENTS.md)** — Streaming and persistence risks, and future improvements.
