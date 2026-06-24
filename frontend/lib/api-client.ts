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
  EndSessionResponse,
  MessagesResponse,
  ModelsResponse,
  Prompt,
  PromptCreateRequest,
  PromptRenderResponse,
  PromptUpdateRequest,
  PromptsResponse,
  SessionSummary,
} from "./types";

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown  // string for most errors; object for structured 409s
  ) {
    super(`API error ${status}: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
    this.name = "ApiError";
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

async function parseErrorDetail(res: Response): Promise<unknown> {
  try {
    const body = await res.clone().json();
    // Return the detail as-is: may be a string or a structured object (e.g. 409)
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

export async function fetchAllPrompts(): Promise<PromptsResponse> {
  const res = await fetch("/api/prompts?all=true");
  return handleResponse(res);
}

export async function createPrompt(body: PromptCreateRequest): Promise<Prompt> {
  const res = await fetch("/api/prompts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse(res);
}

export async function updatePrompt(slug: string, body: PromptUpdateRequest): Promise<Prompt> {
  const res = await fetch(`/api/prompts/${slug}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse(res);
}

export async function disablePrompt(slug: string): Promise<void> {
  const res = await fetch(`/api/prompts/${slug}/disable`, { method: "PATCH" });
  if (!res.ok) throw new ApiError(res.status, await parseErrorDetail(res));
}

export async function enablePrompt(slug: string): Promise<void> {
  const res = await fetch(`/api/prompts/${slug}/enable`, { method: "PATCH" });
  if (!res.ok) throw new ApiError(res.status, await parseErrorDetail(res));
}

export async function deletePrompt(slug: string): Promise<void> {
  const res = await fetch(`/api/prompts/${slug}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(res.status, await parseErrorDetail(res));
}

export async function fetchRenderedPrompt(slug: string): Promise<PromptRenderResponse> {
  const res = await fetch(`/api/prompts/${slug}/render`);
  return handleResponse(res);
}

export async function fetchModels(): Promise<ModelsResponse> {
  const res = await fetch("/api/models");
  return handleResponse(res);
}

// ---------------------------------------------------------------------------
// User status
// ---------------------------------------------------------------------------

export async function fetchUserStatus(userId: string): Promise<{ has_profile: boolean }> {
  const res = await fetch(`/api/u/${userId}/status`);
  return handleResponse(res);
}

// ---------------------------------------------------------------------------
// Conversation list & messages
// ---------------------------------------------------------------------------

export async function fetchConversations(
  userId: string,
  page = 1,
  pageSize = 20
): Promise<ConversationListResponse> {
  const res = await fetch(
    `/api/u/${userId}/conversations?page=${page}&page_size=${pageSize}`
  );
  return handleResponse(res);
}

export async function deleteConversation(userId: string, conversationId: string): Promise<void> {
  const res = await fetch(`/api/u/${userId}/conversations/${conversationId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
}

export async function renameConversation(
  userId: string,
  conversationId: string,
  name: string
): Promise<void> {
  const res = await fetch(`/api/u/${userId}/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  await handleResponse(res);
}

export async function fetchConversationMessages(
  userId: string,
  conversationId: string
): Promise<MessagesResponse> {
  const res = await fetch(`/api/u/${userId}/conversations/${conversationId}/messages`);
  return handleResponse(res);
}

// ---------------------------------------------------------------------------
// Non-streaming chat
// ---------------------------------------------------------------------------

export async function createConversation(
  userId: string,
  body: ConversationRequest
): Promise<ConversationResponse> {
  const res = await fetch(`/api/u/${userId}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse(res);
}

export async function appendConversationTurn(
  userId: string,
  conversationId: string,
  body: ConversationRequest
): Promise<ConversationResponse> {
  const res = await fetch(`/api/u/${userId}/conversations/${conversationId}`, {
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
  userId: string,
  body: ConversationRequest,
  signal?: AbortSignal
): Promise<ReadableStream<Uint8Array>> {
  const res = await fetch(`/api/u/${userId}/conversations/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return getStream(res);
}

export async function initSessionStream(
  userId: string,
  body: { prompt_slug?: string | null; model_slug?: string | null },
  signal?: AbortSignal
): Promise<ReadableStream<Uint8Array>> {
  const res = await fetch(`/api/u/${userId}/conversations/init-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return getStream(res);
}

export async function appendConversationTurnStream(
  userId: string,
  conversationId: string,
  body: ConversationRequest,
  signal?: AbortSignal
): Promise<ReadableStream<Uint8Array>> {
  const res = await fetch(`/api/u/${userId}/conversations/${conversationId}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return getStream(res);
}

export async function fetchSessionSummary(
  userId: string,
  conversationId: string
): Promise<SessionSummary> {
  const res = await fetch(`/api/u/${userId}/conversations/${conversationId}/summary`);
  return handleResponse<SessionSummary>(res);
}

export async function endSession(
  userId: string,
  conversationId: string
): Promise<EndSessionResponse> {
  const res = await fetch(`/api/u/${userId}/conversations/${conversationId}/end-session`, {
    method: "POST",
  });
  return handleResponse<EndSessionResponse>(res);
}

export async function completeSetup(
  userId: string,
  conversationId: string
): Promise<{ status: string }> {
  const res = await fetch(`/api/u/${userId}/conversations/${conversationId}/complete-setup`, {
    method: "POST",
  });
  return handleResponse<{ status: string }>(res);
}

export async function rewindConversationStream(
  userId: string,
  conversationId: string,
  messageId: number,
  content: string,
  promptSlug?: string | null,
  signal?: AbortSignal
): Promise<ReadableStream<Uint8Array>> {
  const res = await fetch(`/api/u/${userId}/conversations/${conversationId}/rewind/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message_id: messageId, content, prompt_slug: promptSlug }),
    signal,
  });
  return getStream(res);
}
