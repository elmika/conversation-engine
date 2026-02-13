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
  We now persist all messages in SQLite, but the LLM context is still built only from the messages included in each request.  
  A next step is to load prior messages via `ConversationRepo.get_messages()` and use them when constructing the Responses API `input` for true multi-turn conversations.

- **Token / finish_reason metadata**  
  The `runs` table has columns for `input_tokens`, `output_tokens`, and `finish_reason`, but the adapter does not yet populate them from the Responses object.  
  We should extract `usage` and any finish reason from the final response and pass them into `ConversationRepo.record_run(...)`.

- **SQLite constraints and growth**  
  SQLite is appropriate for this local demo, but:  
  - High write concurrency or large datasets may require a server-grade database.  
  - We may want simple retention policies (e.g. deleting old conversations) to keep the database small in long-running environments.

## Observability and tests (Day 5+)

- **Append turn context**  
  The integration test documents current behaviour: append sends only the new user message to the LLM, not prior messages.  
  For full history on append, the route (or use case) should call `ConversationRepo.get_messages(cid)`, prepend that to the new messages, and pass the combined list to the LLM.  
  This is already listed under “Conversation history in prompts” above; the test simply asserts current API behaviour.

- **Python 3.9 and type hints**  
  We keep `Optional[...]` for 3.9 compatibility; ruff rule UP045 is ignored.  
  When dropping 3.9, consider switching to `X | None` and re-enabling UP045.

- **GET endpoint for conversations**  
  Consider adding e.g. `GET /conversations/{id}/messages` for easier integration tests and debugging; not required for current test gate.
