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
  Persistence is correctly offloaded to `asyncio.to_thread`, but the OpenAI stream iteration (`for event in stream`) still runs on the event loop.  
  For very long responses or many concurrent streams, we may want to move the entire streaming loop into a worker thread (or a dedicated task with backpressure) so the event loop remains as responsive as possible.

- **Error handling and non-happy-path events**  
  **Done:** Request-level error handling is in place: middleware logs request failures (request_id, endpoint, latency) and re-raises; a global exception handler logs unhandled exceptions and returns a 500 JSON envelope (with optional `request_id`).  
  **Pending:** Non-happy-path streaming events (e.g. `response.failed`, `response.incomplete`) are not yet translated into SSE error events or a terminal `done` with an `error` field. Next steps:  
  - Wrap adapter and OpenAI errors in a structured error payload.  
  - Emit a final `done` SSE event containing `error` information (alongside timings and model metadata).  
  - Optionally surface an `error` SSE event type for clients that want to differentiate failures from normal completion.

- **Multiple streaming entrypoints**  
  We now expose both `POST /conversations/stream` (first turn) and `POST /conversations/{conversation_id}/stream` (subsequent turns).  
  The SSE contract is intentionally identical, but there is still a risk of behavioral drift between the two; any changes to streaming semantics should be applied consistently to both endpoints.

## Persistence – Risks and Future Improvements

- **Conversation history in prompts**  
  **Done:** Append turns now load prior messages via `ConversationRepo.get_messages()` and pass full history (previous user + assistant messages plus the new user turn) to the LLM for both non-streaming and streaming endpoints.  
  **Pending:** Conversation history can grow without bound, and we do not yet cap or trim old turns when building the LLM input; long-running conversations may hit model context limits unless we introduce summarisation or history truncation.

- **Token / finish_reason metadata**  
  The `runs` table has columns for `input_tokens`, `output_tokens`, and `finish_reason`, but the adapter does not yet populate them from the Responses object.  
  We should extract `usage` and any finish reason from the final response and pass them into `ConversationRepo.record_run(...)`.

- **SQLite constraints and growth**  
  SQLite is appropriate for this local demo, but:  
  - High write concurrency or large datasets may require a server-grade database.  
  - We may want simple retention policies (e.g. deleting old conversations) to keep the database small in long-running environments.

## Observability and tests (Day 5+)

- **Testing the OpenAI contract without hitting the API every run**  
  **Done:** We use a **snapshot-style test** for the Responses API payload: `test_adapter_builds_responses_input_payload_shape` asserts that `_build_input_items` produces the correct role-based content types (user/system → `input_text`, assistant → `output_text`). That catches accidental changes to the payload shape without any network call.  
  **Recommendation:** Keep this test as the single source of truth for “what we send”. Optionally add an **opt-in smoke test** (e.g. `@pytest.mark.smoke`, skipped unless `OPENAI_SMOKE=1` and `OPENAI_API_KEY` are set) that performs one minimal create and optionally one append against the real API; run locally or in a nightly job, not on every CI run.

- **Append turn context**  
  The integration test documents current behaviour: append sends only the new user message to the LLM, not prior messages.  
  For full history on append, the route (or use case) should call `ConversationRepo.get_messages(cid)`, prepend that to the new messages, and pass the combined list to the LLM.  
  This is already listed under “Conversation history in prompts” above; the test simply asserts current API behaviour.

- **Python 3.9 and type hints**  
  We keep `Optional[...]` for 3.9 compatibility; ruff rule UP045 is ignored.  
  When dropping 3.9, consider switching to `X | None` and re-enabling UP045.

- **GET endpoint for conversations**  
  Consider adding e.g. `GET /conversations/{id}/messages` for easier integration tests and debugging; not required for current test gate.

## Input caps, timeout, and retry (Day 6+)

- **Stream retry semantics**  
  On a transient error during streaming, we retry from the start (new request). The client cannot “resume” the same stream; they see a new connection. Acceptable for current scope; for stricter guarantees we could document this or add an SSE error event before closing.

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
