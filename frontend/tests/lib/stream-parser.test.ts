import { describe, it, expect } from "vitest";
import { parseSSEStream } from "@/lib/stream-parser";
import type { SSEEvent } from "@/lib/types";

// ---------------------------------------------------------------------------
// Helper: turn an array of strings into a ReadableStream<Uint8Array>
// Each string becomes one chunk, simulating network fragmentation.
// ---------------------------------------------------------------------------

function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<SSEEvent[]> {
  const events: SSEEvent[] = [];
  for await (const event of parseSSEStream(stream)) {
    events.push(event);
  }
  return events;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("parseSSEStream", () => {
  it("parses a complete meta → chunk → done sequence in one chunk", async () => {
    const raw =
      'event: meta\ndata: {"conversation_id":"abc","model":"gpt-4.1-mini","prompt_slug":"default"}\n\n' +
      'event: chunk\ndata: {"delta":"Hello"}\n\n' +
      'event: done\ndata: {"conversation_id":"abc","assistant_message":"Hello","model":"gpt-4.1-mini","timings":{"ttfb_ms":100,"total_ms":300}}\n\n';

    const events = await collect(makeStream([raw]));

    expect(events).toHaveLength(3);
    expect(events[0]).toEqual({
      event: "meta",
      data: { conversation_id: "abc", model: "gpt-4.1-mini", prompt_slug: "default" },
    });
    expect(events[1]).toEqual({ event: "chunk", data: { delta: "Hello" } });
    expect(events[2].event).toBe("done");
    if (events[2].event === "done") {
      expect(events[2].data.assistant_message).toBe("Hello");
      expect(events[2].data.timings?.ttfb_ms).toBe(100);
    }
  });

  it("reassembles events split across multiple network chunks", async () => {
    // Split the raw SSE bytes at arbitrary positions
    const full =
      'event: meta\ndata: {"conversation_id":"x","model":"m","prompt_slug":"default"}\n\n' +
      'event: chunk\ndata: {"delta":"Hi"}\n\n' +
      'event: done\ndata: {"conversation_id":"x","assistant_message":"Hi","model":"m","timings":{"ttfb_ms":10,"total_ms":50}}\n\n';

    // Deliver in 5-character fragments — forces partial-block reassembly
    const chunks: string[] = [];
    for (let i = 0; i < full.length; i += 5) {
      chunks.push(full.slice(i, i + 5));
    }

    const events = await collect(makeStream(chunks));
    expect(events).toHaveLength(3);
    expect(events[0].event).toBe("meta");
    expect(events[1].event).toBe("chunk");
    expect(events[2].event).toBe("done");
  });

  it("handles multiple chunk events", async () => {
    const raw =
      'event: meta\ndata: {"conversation_id":"c","model":"m","prompt_slug":"default"}\n\n' +
      'event: chunk\ndata: {"delta":"One"}\n\n' +
      'event: chunk\ndata: {"delta":" two"}\n\n' +
      'event: chunk\ndata: {"delta":" three"}\n\n' +
      'event: done\ndata: {"conversation_id":"c","assistant_message":"One two three","model":"m","timings":{"ttfb_ms":50,"total_ms":200}}\n\n';

    const events = await collect(makeStream([raw]));

    const chunks = events.filter((e) => e.event === "chunk");
    expect(chunks).toHaveLength(3);
    const deltas = chunks.map((e) => (e.event === "chunk" ? e.data.delta : ""));
    expect(deltas.join("")).toBe("One two three");
  });

  it("parses a done event carrying an error payload", async () => {
    const raw =
      'event: meta\ndata: {"conversation_id":"e","model":"m","prompt_slug":"default"}\n\n' +
      'event: done\ndata: {"error":{"type":"internal_error","message":"Something went wrong"}}\n\n';

    const events = await collect(makeStream([raw]));

    expect(events).toHaveLength(2);
    const done = events[1];
    expect(done.event).toBe("done");
    if (done.event === "done") {
      expect(done.data.error?.type).toBe("internal_error");
      expect(done.data.error?.message).toBe("Something went wrong");
      expect(done.data.assistant_message).toBeUndefined();
    }
  });

  it("skips unknown event types without throwing", async () => {
    const raw =
      'event: ping\ndata: {"ts":1234}\n\n' +
      'event: chunk\ndata: {"delta":"ok"}\n\n' +
      'event: done\ndata: {"conversation_id":"d","assistant_message":"ok","model":"m","timings":{"ttfb_ms":1,"total_ms":2}}\n\n';

    const events = await collect(makeStream([raw]));
    // ping is skipped
    expect(events).toHaveLength(2);
    expect(events[0].event).toBe("chunk");
  });

  it("skips blocks with malformed JSON without throwing", async () => {
    const raw =
      "event: chunk\ndata: {broken json\n\n" +
      'event: done\ndata: {"conversation_id":"d","assistant_message":"ok","model":"m","timings":{"ttfb_ms":1,"total_ms":2}}\n\n';

    const events = await collect(makeStream([raw]));
    expect(events).toHaveLength(1);
    expect(events[0].event).toBe("done");
  });

  it("handles a stream that ends without a trailing double-newline", async () => {
    // The final event block has no trailing \n\n — the remaining buffer should still be parsed
    const raw =
      'event: meta\ndata: {"conversation_id":"f","model":"m","prompt_slug":"default"}\n\n' +
      'event: done\ndata: {"conversation_id":"f","assistant_message":"hi","model":"m","timings":{"ttfb_ms":1,"total_ms":2}}';

    const events = await collect(makeStream([raw]));
    expect(events).toHaveLength(2);
    expect(events[1].event).toBe("done");
  });

  it("handles UTF-8 characters split across chunk boundaries", async () => {
    const payload = JSON.stringify({ delta: "こんにちは" }); // multi-byte chars
    const line = `event: chunk\ndata: ${payload}\n\n`;
    const bytes = new TextEncoder().encode(line);

    // Split at byte 10, which lands in the middle of a UTF-8 sequence
    const part1 = bytes.slice(0, 10);
    const part2 = bytes.slice(10);

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(part1);
        controller.enqueue(part2);
        // Append a done event to flush
        controller.enqueue(
          new TextEncoder().encode(
            'event: done\ndata: {"conversation_id":"g","assistant_message":"こんにちは","model":"m","timings":{"ttfb_ms":1,"total_ms":2}}\n\n'
          )
        );
        controller.close();
      },
    });

    const events = await collect(stream);
    const chunk = events.find((e) => e.event === "chunk");
    expect(chunk?.event === "chunk" && chunk.data.delta).toBe("こんにちは");
  });

  it("returns no events for an empty stream", async () => {
    const events = await collect(makeStream([]));
    expect(events).toHaveLength(0);
  });
});
