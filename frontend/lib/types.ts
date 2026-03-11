/**
 * TypeScript interfaces mirroring the FastAPI Pydantic schemas and SSE wire shapes.
 * Keep in sync with app/api/schemas.py whenever the backend API changes.
 */

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export type MessageRole = "user" | "assistant" | "system";

export interface ConversationMessage {
  role: MessageRole;
  content: string;
}

export interface ConversationRequest {
  prompt_slug?: string | null;
  messages: ConversationMessage[];
}

// ---------------------------------------------------------------------------
// Non-streaming response types
// ---------------------------------------------------------------------------

export interface Timings {
  ttfb_ms: number;
  total_ms: number;
}

export interface ConversationResponse {
  conversation_id: string;
  assistant_message: string;
  model: string;
  timings: Timings;
}

export interface ConversationSummary {
  id: string;
  name?: string | null;
  created_at: string; // ISO 8601
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface Message {
  id: number;
  role: MessageRole;
  content: string;
  created_at: string; // ISO 8601
}

export interface MessagesResponse {
  conversation_id: string;
  messages: Message[];
}

export interface Prompt {
  slug: string;
  name: string;
  system_prompt: string;
}

export interface PromptsResponse {
  prompts: Prompt[];
}

// ---------------------------------------------------------------------------
// SSE event data payloads
// ---------------------------------------------------------------------------

/** Payload of the first `meta` event on a streaming connection. */
export interface SSEMetaData {
  conversation_id: string;
  model: string;
  prompt_slug: string;
}

/** Payload of each `chunk` event — incremental text fragment. */
export interface SSEChunkData {
  delta: string;
}

/** Error object present on the `done` event when the stream ended in failure. */
export interface SSEErrorPayload {
  type: "http_error" | "internal_error";
  status_code?: number;
  message: string;
}

/**
 * Payload of the terminal `done` event.
 * On success: conversation_id, assistant_message, model, timings are all present.
 * On failure: only `error` is present.
 */
export interface SSEDoneData {
  conversation_id?: string;
  assistant_message?: string;
  model?: string;
  timings?: Timings;
  error?: SSEErrorPayload;
}

// ---------------------------------------------------------------------------
// Discriminated union used by parseSSEStream
// ---------------------------------------------------------------------------

export interface MetaEvent {
  event: "meta";
  data: SSEMetaData;
}

export interface ChunkEvent {
  event: "chunk";
  data: SSEChunkData;
}

export interface DoneEvent {
  event: "done";
  data: SSEDoneData;
}

export type SSEEvent = MetaEvent | ChunkEvent | DoneEvent;

// ---------------------------------------------------------------------------
// API error
// ---------------------------------------------------------------------------

export interface ApiErrorBody {
  detail: string;
  request_id?: string;
}
