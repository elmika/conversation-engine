import type { SSEEvent, MetaEvent, ChunkEvent, DoneEvent } from "./types";

/**
 * Parses a Server-Sent Events stream from the FastAPI backend.
 *
 * Yields typed SSEEvent objects: MetaEvent | ChunkEvent | DoneEvent.
 *
 * Design notes:
 * - Accumulates raw bytes into a text buffer using a streaming TextDecoder so
 *   multi-byte UTF-8 characters spanning chunk boundaries are handled correctly.
 * - Splits on `\n\n` (the SSE event boundary) keeping any partial block in the
 *   buffer for the next read.
 * - Parsing is intentionally lenient: unknown event types and malformed JSON are
 *   silently skipped so a single bad frame never kills the stream.
 *
 * @param stream - ReadableStream<Uint8Array> from a fetch Response body.
 */
export async function* parseSSEStream(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<SSEEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // { stream: true } defers flushing so multi-byte sequences are not split
      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by a blank line (\n\n)
      const blocks = buffer.split("\n\n");

      // The last element may be an incomplete block — keep it for next iteration
      buffer = blocks.pop() ?? "";

      for (const block of blocks) {
        const event = parseBlock(block);
        if (event) yield event;
      }
    }

    // Flush the decoder and process any remaining content
    buffer += decoder.decode();
    if (buffer.trim()) {
      const event = parseBlock(buffer);
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function parseBlock(block: string): SSEEvent | null {
  let eventType = "";
  let dataStr = "";

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      eventType = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataStr = line.slice("data:".length).trim();
    }
  }

  if (!eventType || !dataStr) return null;

  let data: unknown;
  try {
    data = JSON.parse(dataStr);
  } catch {
    // Malformed JSON — skip the block
    return null;
  }

  switch (eventType) {
    case "meta":
      return { event: "meta", data } as MetaEvent;
    case "chunk":
      return { event: "chunk", data } as ChunkEvent;
    case "done":
      return { event: "done", data } as DoneEvent;
    default:
      return null;
  }
}
