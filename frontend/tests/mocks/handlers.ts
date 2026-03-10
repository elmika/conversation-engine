import { http, HttpResponse } from "msw";

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

const CONVERSATION_ID = "test-conv-id-1";

const PROMPTS_FIXTURE = {
  prompts: [
    { slug: "default", name: "Default", system_prompt: "You are a helpful assistant." },
    { slug: "concise", name: "Concise", system_prompt: "Reply briefly." },
  ],
};

const CONVERSATIONS_FIXTURE = {
  conversations: [
    { id: CONVERSATION_ID, created_at: "2024-01-01T00:00:00" },
    { id: "test-conv-id-2", created_at: "2024-01-02T00:00:00" },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

const MESSAGES_FIXTURE = {
  conversation_id: CONVERSATION_ID,
  messages: [
    { id: 1, role: "user", content: "Hello", created_at: "2024-01-01T00:00:01" },
    { id: 2, role: "assistant", content: "Hi there!", created_at: "2024-01-01T00:00:02" },
  ],
};

// ---------------------------------------------------------------------------
// SSE helper — builds a ReadableStream that emits SSE frames
// ---------------------------------------------------------------------------

function sseStream(events: Array<{ event: string; data: object }>): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const { event, data } of events) {
        controller.enqueue(
          encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
        );
      }
      controller.close();
    },
  });
  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
    },
  });
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

export const handlers = [
  // Health
  http.get("/api/healthz", () => HttpResponse.json({ status: "ok" })),

  // Prompts
  http.get("/api/prompts", () => HttpResponse.json(PROMPTS_FIXTURE)),

  // Conversation list
  http.get("/api/conversations", () => HttpResponse.json(CONVERSATIONS_FIXTURE)),

  // Create conversation (non-streaming)
  http.post("/api/conversations", () =>
    HttpResponse.json({
      conversation_id: CONVERSATION_ID,
      assistant_message: "Hello!",
      model: "gpt-4.1-mini",
      timings: { ttfb_ms: 50, total_ms: 200 },
    })
  ),

  // Append turn (non-streaming)
  http.post("/api/conversations/:conversationId", () =>
    HttpResponse.json({
      conversation_id: CONVERSATION_ID,
      assistant_message: "Follow-up reply.",
      model: "gpt-4.1-mini",
      timings: { ttfb_ms: 40, total_ms: 150 },
    })
  ),

  // Get messages
  http.get("/api/conversations/:conversationId/messages", () =>
    HttpResponse.json(MESSAGES_FIXTURE)
  ),

  // Create conversation stream
  http.post("/api/conversations/stream", () =>
    sseStream([
      { event: "meta", data: { conversation_id: CONVERSATION_ID, model: "gpt-4.1-mini", prompt_slug: "default" } },
      { event: "chunk", data: { delta: "Hello" } },
      { event: "chunk", data: { delta: " world" } },
      { event: "done", data: { conversation_id: CONVERSATION_ID, assistant_message: "Hello world", model: "gpt-4.1-mini", timings: { ttfb_ms: 50, total_ms: 200 } } },
    ])
  ),

  // Append turn stream
  http.post("/api/conversations/:conversationId/stream", () =>
    sseStream([
      { event: "meta", data: { conversation_id: CONVERSATION_ID, model: "gpt-4.1-mini", prompt_slug: "default" } },
      { event: "chunk", data: { delta: "Follow-up" } },
      { event: "done", data: { conversation_id: CONVERSATION_ID, assistant_message: "Follow-up", model: "gpt-4.1-mini", timings: { ttfb_ms: 30, total_ms: 120 } } },
    ])
  ),
];
