
# Top Risks and Improvements

TBD.


# Exhaustive Risks and Improvements

## Streaming – Risks and Future Improvements

- **OpenAI SDK streaming shape**
  The adapter assumes `event.type == "response.output_text.delta"` and uses `event.delta`.
  If the SDK changes event names or payload fields, we will need a small adjustment in `OpenAILLMAdapter.stream`.
  Unit tests stay stable because they mock the adapter rather than hitting the real API.

- **Backpressure / long streams**
  The current implementation streams tokens as they arrive with no explicit backpressure controls.
  This is acceptable for a demo, but heavier workloads may require:
  - Rate limiting or throttling of outbound SSE events.
  - Chunk aggregation (buffering partial deltas) to reduce event volume.
  - Timeouts or maximum stream durations to protect the service.

- **Event-loop usage during streaming**
  The service call setup is correctly offloaded via `asyncio.to_thread`, but the OpenAI stream iteration (`for event in stream`) still runs on the event loop inside the `async def event_generator()` coroutine.
  For very long responses or many concurrent streams, we may want to move the entire streaming loop into a worker thread (or a dedicated task with backpressure) so the event loop remains as responsive as possible.

- **Error handling and non-happy-path events**
  **Done:** Streaming endpoints now emit terminal `done` events with structured error payloads.
  - Both streaming endpoints wrap event generation in try/catch
  - HTTPException and general exceptions emit `done` event with `error` field
  - Error payload includes `type` (http_error/internal_error), `status_code`, and `message`
  - General exceptions are re-raised after emitting error event for middleware logging

  **Future improvements:**
  - **Error classification granularity**: Add more specific error types (e.g., `validation_error`, `not_found`, `rate_limit`) instead of generic `http_error` for better client-side handling
  - **Partial content recovery**: If stream fails mid-way after emitting chunks, include partial `assistant_message` in error payload so clients can show what was received before failure
  - **Retry hints**: Include `retry_after` seconds in rate limit errors to guide client retry behavior
  - **Conversation ID in early errors**: For errors before meta event is emitted, still include `conversation_id` in error payload if available (e.g., for append endpoints where ID is known upfront)

- **Multiple streaming entrypoints**
  We now expose both `POST /conversations/stream` (first turn) and `POST /conversations/{conversation_id}/stream` (subsequent turns).
  The SSE contract is intentionally identical, but there is still a risk of behavioral drift between the two; any changes to streaming semantics should be applied consistently to both endpoints.

## Persistence – Risks and Future Improvements

- **Conversation history in prompts**
  **Done:** Append turns load prior messages via `ConversationRepo.get_messages()` and pass full history to the LLM. History is capped by `max_history_turns` and `max_history_tokens` via `trim_history()` in `domain/history.py`.

- **Token / finish_reason metadata**
  The `runs` table has columns for `input_tokens`, `output_tokens`, and `finish_reason`, and `record_run()` accepts these parameters — but `OpenAILLMAdapter` does not yet extract `usage` or `finish_reason` from the Responses object, so these fields are always persisted as `None`.
  We should extract `usage` and finish reason from the final response and pass them into `record_run(...)`.

- **SQLite constraints and growth**
  SQLite is appropriate for this local demo, but:
  - High write concurrency or large datasets may require a server-grade database.
  - We may want simple retention policies (e.g. deleting old conversations) to keep the database small in long-running environments.

- **Real database for production**
  Setting up a "real" database (e.g. PostgreSQL) is a worthwhile improvement for production or once we store more than conversations/runs (e.g. prompts). Enables better concurrency, tooling, and backups; SQLite remains fine for local/dev and tests.

## Architecture

- **Prompts from infrastructure with a contract**
  **Done:** `PromptRepo` port exists in `application/ports.py` with `get_prompt()`, `get_prompt_or_default()`, `list_prompts()`, and `upsert()`. A `prompts` table is defined in the ORM and `SQLAlchemyPromptRepo` is the concrete adapter. Services load prompts via the port; the in-code registry is no longer the source of truth.

## Prompts and configuration

- **Prompts from database (no YAML)**
  **Done:** Prompts are DB-backed. A `Prompt` ORM model and `prompts` table exist. `SQLAlchemyPromptRepo` in `infra/persistence/repo_prompt.py` implements the `PromptRepo` port. Prompts are seeded from `.md` files in `prompts/` on startup and served via `GET /prompts`. Adding a new assistant requires only dropping a `.md` file and restarting — no code changes.
  **Remaining:** The admin panel is read-only; full CRUD for prompts via the UI is not yet implemented.

## Observability and tests (Day 5+)

- **Testing the OpenAI contract without hitting the API every run**
  **Done:** We use a **snapshot-style test** for the Responses API payload: `test_adapter_builds_responses_input_payload_shape` asserts that `_build_input_items` produces the correct role-based content types (user/system → `input_text`, assistant → `output_text`). That catches accidental changes to the payload shape without any network call.
  **Recommendation:** Keep this test as the single source of truth for "what we send". Optionally add an **opt-in smoke test** (e.g. `@pytest.mark.smoke`, skipped unless `OPENAI_SMOKE=1` and `OPENAI_API_KEY` are set) that performs one minimal create and optionally one append against the real API; run locally or in a nightly job, not on every CI run. No such test exists yet.

- **Validating against OpenAI's published OpenAPI spec**
  **Confirmed:** OpenAI publishes an OpenAPI 3.0 spec. The **Responses API is described** there: paths `POST /responses`, `GET/PATCH /responses/{response_id}`, and `GET /responses/{response_id}/input_items` are present in the manual spec.
  - **Spec location:** [openai/openai-openapi](https://github.com/openai/openai-openapi) — `openapi.yaml` on branch **manual_spec**; "most recent" documented version at `https://app.stainless.com/api/spec/documented/openai/openapi.documented.yml` (see repo README).
  - **We are not using it today:** we do not fetch or validate our request payload against this spec; we rely only on the snapshot test above.
  - **Recommended workflow (future improvement):**
    1. **CI (no API key):** Keep the snapshot test; optionally add a step that fetches the published spec (e.g. from `manual_spec` or Stainless URL), resolves the request body schema for `POST /responses`, and validates that the output of `_build_input_items` (for a few representative message lists) conforms to that schema via a JSON Schema validator. That would catch drift from OpenAI's contract without calling the live API.
    2. **Optional smoke (when enabled):** Run one real create (and optionally append) against the API when `OPENAI_SMOKE=1` and `OPENAI_API_KEY` are set; run locally or in a nightly job only.
  Before adding schema validation, confirm the spec's `POST /responses` request body schema exists and matches the Responses API docs (input message content types, etc.).

- **Append turn context**
  **Done:** Append turns load the full conversation history via `ConversationRepo.get_messages()` and pass it to the LLM. The integration test reflects this behaviour.

- **Python 3.9 and type hints**
  We keep `Optional[...]` for 3.9 compatibility; ruff rule UP045 is ignored.
  When dropping 3.9, consider switching to `X | None` and re-enabling UP045.

- **GET endpoint for conversations**
  **Done:** `GET /conversations/{id}/messages` is implemented in `app/api/routes.py`. Returns messages ordered by id ASC with full metadata (id, role, content, created_at).

## Input caps, timeout, and retry (Day 6+)

- **Stream retry semantics**
  On a transient error during streaming, we retry from the start (new request). The client cannot "resume" the same stream; they see a new connection. Acceptable for current scope; for stricter guarantees we could document this or add an SSE error event before closing.

- **Input cap is character-based**
  `max_input_chars` is enforced as total character count of message contents only (no system prompt, no tokenization), and is currently applied only to the new turn's messages. For strict token limits, cost control, or very long histories, we should consider a token-based check on the full prompt (history + new turn) and possibly summarisation/truncation of older context.

- **Timeout and SDK behaviour**
  We pass `request_timeout_s` to the OpenAI client for both `create` and `stream`. The SDK has known quirks where timeouts are not always honoured; monitor and consider client-level timeouts or wrapping in `asyncio.wait_for` if needed.

## Load testing and performance (Day 10+)

- **Light-load focus only**
  Current guidance and examples target light load (dozens of requests, small concurrency). They are useful for smoke-testing and getting a feel for TTFB/latency but are not a substitute for proper performance and capacity testing.

- **No dedicated monitoring/metrics yet**
  We rely on structured logs (request_id, endpoint, status, latency) and per-request `timings` fields to reason about performance. For higher loads or production use, we would want real metrics (e.g. Prometheus, tracing) and dashboards.

- **OpenAI limits and upstream variability**
  Under heavier load, OpenAI rate limits or upstream variability (queueing, retries) may dominate latency and error patterns. The current retry/backoff is basic; a more robust setup would combine backoff with better observability and, if needed, workload shaping or queuing.


## Persistence – Transaction boundaries (Unit of Work)

**Done:** Unit of Work is implemented. `UnitOfWork` port in `application/ports.py` owns the SQLAlchemy session lifecycle; `SQLAlchemyUnitOfWork` in `infra/persistence/repo_sqlalchemy.py` is the concrete adapter. Repositories no longer commit; service methods define transaction boundaries.


## Persistence – Async/sync boundary

- Current risk: SQLAlchemy session usage is synchronous (and SQLite is sync). If used directly on the event loop, it can block under load.
- Current mitigation: all DB operations in routes are offloaded via `asyncio.to_thread`.
- Improvement: enforce this as a rule (or migrate to SQLAlchemy async engine + async driver when moving to Postgres). Add a small test or lint guideline to prevent accidental sync DB calls on the event loop.
