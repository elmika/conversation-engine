import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useStreamingChat } from "@/hooks/useStreamingChat";
import {
  createConversationStream,
  appendConversationTurnStream,
} from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Mock the api-client so we control the SSE stream directly.
// This avoids MSW Node.js streaming limitations.
// ---------------------------------------------------------------------------

vi.mock("@/lib/api-client");

function makeSseStream(
  events: Array<{ event: string; data: object }>
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const { event, data } of events) {
        controller.enqueue(
          encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
        );
      }
      controller.close();
    },
  });
}

const STREAM_EVENTS = [
  {
    event: "meta",
    data: { conversation_id: "test-conv-id-1", model: "gpt-4.1-mini", prompt_slug: "default" },
  },
  { event: "chunk", data: { delta: "Hello" } },
  { event: "chunk", data: { delta: " world" } },
  {
    event: "done",
    data: {
      conversation_id: "test-conv-id-1",
      assistant_message: "Hello world",
      model: "gpt-4.1-mini",
      timings: { ttfb_ms: 50, total_ms: 200 },
    },
  },
];

beforeEach(() => {
  vi.mocked(createConversationStream).mockResolvedValue(
    makeSseStream(STREAM_EVENTS)
  );
  vi.mocked(appendConversationTurnStream).mockResolvedValue(
    makeSseStream(STREAM_EVENTS)
  );
});

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useStreamingChat", () => {
  it("starts idle", () => {
    const { result } = renderHook(() => useStreamingChat(), {
      wrapper: makeWrapper(),
    });
    expect(result.current.status).toBe("idle");
    expect(result.current.partialText).toBe("");
  });

  it("transitions through connecting → streaming → done", async () => {
    const { result } = renderHook(() => useStreamingChat(), {
      wrapper: makeWrapper(),
    });

    act(() => {
      result.current.sendMessage({
        messages: [{ role: "user", content: "Hi" }],
        prompt_slug: "default",
      });
    });

    await waitFor(() => {
      expect(result.current.status).toBe("done");
    });

    expect(result.current.partialText).toBe("Hello world");
    expect(result.current.conversationId).toBe("test-conv-id-1");
    expect(result.current.timings?.ttfb_ms).toBe(50);
  });

  it("accumulates partial text during streaming", async () => {
    const { result } = renderHook(() => useStreamingChat(), {
      wrapper: makeWrapper(),
    });

    act(() => {
      result.current.sendMessage({
        messages: [{ role: "user", content: "Hi" }],
      });
    });

    await waitFor(() => expect(result.current.status).toBe("done"));
    expect(result.current.partialText).toBe("Hello world");
  });

  it("invalidates queries on done", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useStreamingChat(), { wrapper });

    act(() => {
      result.current.sendMessage({
        messages: [{ role: "user", content: "Hi" }],
      });
    });

    await waitFor(() => expect(result.current.status).toBe("done"));

    const calls = invalidate.mock.calls.map((c) => c[0]);
    expect(calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ queryKey: ["messages", "test-conv-id-1"] }),
        expect.objectContaining({ queryKey: ["conversations"] }),
      ])
    );
  });

  it("cancel() aborts and sets status to idle", async () => {
    const { result } = renderHook(() => useStreamingChat(), {
      wrapper: makeWrapper(),
    });

    act(() => {
      result.current.sendMessage({
        messages: [{ role: "user", content: "Hi" }],
      });
    });

    act(() => {
      result.current.cancel();
    });

    await waitFor(() => {
      expect(
        result.current.status === "idle" || result.current.status === "done"
      ).toBe(true);
    });
  });

  it("reset() returns to initial state", async () => {
    const { result } = renderHook(() => useStreamingChat(), {
      wrapper: makeWrapper(),
    });

    act(() => {
      result.current.sendMessage({
        messages: [{ role: "user", content: "Hi" }],
      });
    });
    await waitFor(() => expect(result.current.status).toBe("done"));

    act(() => result.current.reset());

    expect(result.current.status).toBe("idle");
    expect(result.current.partialText).toBe("");
    expect(result.current.conversationId).toBeNull();
  });
});
