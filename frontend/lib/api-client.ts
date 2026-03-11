/**
 * Typed fetch wrappers for all BFF Route Handler endpoints.
 *
 * All paths are relative (`/api/...`) so they always resolve against the
 * Next.js origin — the FastAPI URL is never referenced from the browser.
 *
 * Streaming helpers return `ReadableStream<Uint8Array>` (the raw Response body)
 * so callers can pipe straight into `parseSSEStream` without buffering.
 */

import type {
  ConversationListResponse,
  ConversationRequest,
  ConversationResponse,
  MessagesResponse,
  PromptsResponse,
} from "./types";

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string
  ) {
    super(`API error ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.clone().json();
    return body.detail ?? res.statusText;
  } catch {
    return res.statusText;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return res.json() as Promise<T>;
}

async function getStream(res: Response): Promise<ReadableStream<Uint8Array>> {
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  if (!res.body) {
    throw new ApiError(500, "Response body is null");
  }
  return res.body;
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch("/api/healthz");
  return handleResponse(res);
}

// ---------------------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------------------

export async function fetchPrompts(): Promise<PromptsResponse> {
  const res = await fetch("/api/prompts");
  return handleResponse(res);
}

// ---------------------------------------------------------------------------
// Conversation list & messages
// ---------------------------------------------------------------------------

export async function fetchConversations(
  page = 1,
  pageSize = 20
): Promise<ConversationListResponse> {
  const res = await fetch(
    `/api/conversations?page=${page}&page_size=${pageSize}`
  );
  return handleResponse(res);
}

export async function renameConversation(
  conversationId: string,
  name: string
): Promise<void> {
  const res = await fetch(`/api/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  await handleResponse(res);
}

export async function fetchConversationMessages(
  conversationId: string
): Promise<MessagesResponse> {
  const res = await fetch(`/api/conversations/${conversationId}/messages`);
  return handleResponse(res);
}

// ---------------------------------------------------------------------------
// Non-streaming chat
// ---------------------------------------------------------------------------

export async function createConversation(
  body: ConversationRequest
): Promise<ConversationResponse> {
  const res = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse(res);
}

export async function appendConversationTurn(
  conversationId: string,
  body: ConversationRequest
): Promise<ConversationResponse> {
  const res = await fetch(`/api/conversations/${conversationId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse(res);
}

// ---------------------------------------------------------------------------
// Streaming chat — returns the raw body so callers pipe to parseSSEStream
// ---------------------------------------------------------------------------

export async function createConversationStream(
  body: ConversationRequest,
  signal?: AbortSignal
): Promise<ReadableStream<Uint8Array>> {
  const res = await fetch("/api/conversations/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return getStream(res);
}

export async function appendConversationTurnStream(
  conversationId: string,
  body: ConversationRequest,
  signal?: AbortSignal
): Promise<ReadableStream<Uint8Array>> {
  const res = await fetch(`/api/conversations/${conversationId}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return getStream(res);
}
