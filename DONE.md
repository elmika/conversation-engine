# First refactor (27 feb 2026)

## Top Risks and Improvements

1.Routes too fat (duplication + orchestration in API layer) ✅ FIXED

This is the biggest “complexity multiplier”.

-It drives bugs (create vs append drift, stream vs non-stream drift)
-It makes tests harder
-It blocks clean transaction boundaries

Fix: move “load history → call LLM → persist → format response” into application services/use cases. Routes become glue.

**Implementation details:**
- Created `ConversationService` in `app/application/services.py` with methods: `create_and_chat()`, `append_and_chat()`, `create_and_stream()`, `append_and_stream()`, `persist_stream_result()`
- Routes now delegate all orchestration to the service layer
- Service encapsulates: conversation creation, message persistence, history loading, LLM invocation, response persistence
- Routes handle only: input validation, calling service methods, formatting HTTP/SSE responses
- Eliminated code duplication between create/append and stream/non-stream endpoints
- Clearer separation of concerns: routes = HTTP layer, service = business workflow orchestration
- Easier to test: service methods can be unit-tested independently of HTTP
- Prepares for transaction boundaries: UoW can be introduced in the service layer without touching routes

2.Transaction boundaries / UoW (commit discipline) ✅ FIXED

**Status:** Resolved by implementing the Unit of Work pattern. Repository no longer commits; service methods define transaction boundaries.

-Prevents partial persistence (especially around streaming + errors)
-Makes retries + error handling sane
-Enables future “atomic: messages + run + conversation state”

Fix: introduce UoW; remove repo commits.

3.Conversation history growth / token limits (cost + failure mode) ✅ FIXED

**Status:** Resolved by implementing configurable history capping with both turn and token limits.

**What changed:**
- Added `max_history_turns` (default: 20) and `max_history_tokens` (default: 100,000) to settings
- Created `trim_history()` utility in `app/domain/history.py` that keeps most recent N turns within token budget
- Services automatically trim history before calling LLM
- Token estimation uses 4 chars/token heuristic (conservative, safe for limits)

**Practical limits for gpt-4.1-mini (128K context):**
- **20 turns:** Keeps conversations focused (10 back-and-forth exchanges)
- **100K tokens:** ~75% of 128K context, leaves room for system prompt + new turn + response + safety margin

**Benefits:**
- **Prevents context overflow:** Never hit the 128K token limit
- **Cost control:** Limits max tokens per request, preventing cost explosion
- **Latency control:** Smaller context = faster responses
- **Configurable:** Can adjust limits via environment variables for different use cases

4.Streaming non-happy-path events + client contract ✅ FIXED

**Done:** Standardized SSE end-of-stream semantics with error envelope.
- All streaming endpoints (`/conversations/stream` and `/conversations/{id}/stream`) now wrap event generation in try/catch
- HTTPException and general exceptions emit terminal `done` event with `error` field instead of `assistant_message`
- Error payload includes `type` (http_error/internal_error), `status_code` (if applicable), and `message`
- Clients always receive a terminal event, preventing hangs or ambiguous completion states
- Tests verify error scenarios for both create and append streaming endpoints
- API.md documents the error contract with examples

**Benefits:**
- Clients never hang waiting for more data
- Clear distinction between successful completion and failures
- Structured error information for client-side handling
- Consistent UX across all error types (rate limits, timeouts, internal errors)

## Architecture

- **Routes too fat** ✅ FIXED  
  **Done:** Introduced `ConversationService` in `app/application/services.py`. Routes are now thin—they validate input, call service methods (`create_and_chat`, `append_and_chat`, `create_and_stream`, `append_and_stream`), and format HTTP/SSE responses. All orchestration (conversation creation, message persistence, history loading, LLM invocation, response persistence) lives in the service layer. This eliminates duplication between create/append and stream/non-stream endpoints and makes the API layer easier to test and change.

- **Domain very thin** ✅ STRENGTHENED  
  **Done:** Introduced domain value objects and entities in `app/domain/`. The domain now has a clear "center" with business rules and invariants: **Value objects:** `ConversationId` (UUID generation + validation), `PromptSlug` (registry validation), `MessageRole` (enum with validation). **Entities:** `Message` (validated role + content), `ConversationTurn` (user messages + assistant response with invariants), `Conversation` (aggregate root with ID + turn history). **Business rules:** Conversation ID generation moved from infrastructure to domain; prompt slug validation is explicit; message roles are type-safe enums. Use cases and services now depend on domain types instead of primitive strings, making business concepts explicit and enforcing invariants at compile time.

