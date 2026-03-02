# Frontend

Next.js 15 App Router UI for the Conversation Engine. Runs on port 3000 and proxies all API calls to the FastAPI backend through BFF Route Handlers — the FastAPI URL is never exposed to the browser.

## Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 15, App Router, TypeScript |
| Styling | Tailwind CSS + shadcn/ui (Radix primitives) |
| Server state | TanStack Query v5 |
| UI state | Zustand v5 |
| Tests | Vitest + Testing Library + MSW v2 |
| Package manager | pnpm |

## Pages

| Route | Description |
|---|---|
| `/` | Redirects to `/chat` |
| `/chat` | New conversation — blank slate, choose a persona and start typing |
| `/chat/[conversationId]` | Existing conversation — loads full message history, streaming continues from the same thread |
| `/history` | Paginated conversation browser, sorted newest first |
| `/admin` | Lists all registered prompt personas with expandable system prompts; placeholder for aggregate stats |

## BFF Route Handlers

All browser API calls go through `app/api/` Route Handlers at `/api/...`. These are server-side only; they read `FASTAPI_URL` from `process.env` and the FastAPI URL never reaches the client.

| Method | BFF path | FastAPI path | Notes |
|---|---|---|---|
| GET | `/api/healthz` | `/healthz` | Passthrough |
| GET | `/api/prompts` | `/prompts` | Passthrough |
| GET | `/api/conversations` | `/conversations` | Forwards `page` + `page_size` query params |
| POST | `/api/conversations` | `/conversations` | Non-streaming create |
| POST | `/api/conversations/stream` | `/conversations/stream` | Pipes `upstream.body` directly — no buffering |
| GET | `/api/conversations/[conversationId]/messages` | `/conversations/:id/messages` | Passthrough |
| POST | `/api/conversations/[conversationId]` | `/conversations/:id` | Non-streaming append |
| POST | `/api/conversations/[conversationId]/stream` | `/conversations/:id/stream` | Pipes `upstream.body` directly — no buffering |

Request/response shapes are identical to the FastAPI API — see `docs/openapi.yml`.

## State Management

**Zustand** (`hooks/useChatStore.ts`) holds UI-only state that does not need to be cached or invalidated:

| Field | Default | Purpose |
|---|---|---|
| `activeConversationId` | `null` | Which conversation is open |
| `selectedPromptSlug` | `"default"` | Current persona selection |
| `isSidebarOpen` | `true` | Sidebar visibility toggle |

**TanStack Query** manages all server state. Queries and their cache keys:

| Hook | Cache key | Stale time |
|---|---|---|
| `usePrompts` | `["prompts"]` | Infinity — prompts don't change at runtime |
| `useConversationList(page)` | `["conversations", page, pageSize]` | 30s |
| `useConversation(id)` | `["messages", id]` | 30s |

After a streaming response completes, `useStreamingChat` invalidates `["messages", conversationId]` and (for new conversations) `["conversations"]` so the sidebar and message list update automatically.

## Streaming

`hooks/useStreamingChat.ts` is the core streaming hook. It implements a state machine:

```
idle → connecting → streaming → done
                              ↘ error
```

- `connecting` — fetch in flight, waiting for first byte
- `streaming` — accumulating `chunk` deltas into `partialText`
- `done` — stream finished; `partialText`, `conversationId`, and `timings` are populated
- `error` — `errorMessage` is populated (from SSE `done.error` or fetch failure)

`cancel()` aborts the in-flight request via `AbortController` and returns to `idle`.
`reset()` returns to the initial `idle` state from any terminal state.

SSE parsing lives in `lib/stream-parser.ts` — an async generator that handles UTF-8 sequences split across chunk boundaries, lenient JSON, and streams that end without a trailing `\n\n`.

## Key Source Files

| File | Purpose |
|---|---|
| `lib/types.ts` | TypeScript interfaces mirroring all API schemas and SSE event shapes |
| `lib/stream-parser.ts` | `parseSSEStream()` — `ReadableStream<Uint8Array>` → typed SSE events |
| `lib/api-client.ts` | `ApiError` + typed fetch wrappers for every BFF route |
| `lib/utils.ts` | `cn()`, `formatDate()`, `truncateId()` |
| `hooks/useStreamingChat.ts` | State machine for streaming chat |
| `components/chat/ChatShell.tsx` | Top-level chat layout: sidebar + message list + input |
| `components/chat/MessageList.tsx` | Scrollable message list with streaming and loading states |

## Development

All commands run in Docker — no local Node.js required.

```bash
# Start everything (hot-reload on both frontend and backend)
docker compose up

# Run all frontend tests
docker compose run --rm frontend pnpm exec vitest run

# Run a single test file
docker compose run --rm frontend pnpm exec vitest run tests/lib/stream-parser.test.ts

# Add a dependency
docker compose run --rm frontend pnpm add <package>
docker compose run --rm frontend pnpm add -D <package>
```

Environment: copy `frontend/.env.local.example` to `frontend/.env.local` if running the frontend standalone (outside Compose). Compose injects `FASTAPI_URL=http://api:8000` automatically.

## Testing

Tests live in `frontend/tests/` mirroring the source structure.

| File | What it covers |
|---|---|
| `tests/lib/stream-parser.test.ts` | SSE parsing: fragmented chunks, UTF-8 boundaries, malformed JSON, error done events |
| `tests/hooks/useStreamingChat.test.tsx` | State machine transitions, partial text accumulation, query invalidation, cancel/reset |
| `tests/components/ChatInput.test.tsx` | Send on Enter, Shift+Enter newline, disabled state, whitespace guard |
| `tests/components/MessageBubble.test.tsx` | Role-based alignment, markdown rendering for assistant, plain text for user |
| `tests/components/ConversationList.test.tsx` | Skeleton on load, link rendering, active conversation highlight |

MSW v2 handlers (`tests/mocks/handlers.ts`) intercept all BFF routes. For streaming tests, the `createConversationStream`/`appendConversationTurnStream` functions are mocked directly (MSW Node.js mode does not fully support streaming response bodies).

Use `tests/utils.tsx` `renderWithProviders()` to wrap components with a fresh `QueryClient` in component tests.
