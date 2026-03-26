import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageList } from "@/components/chat/MessageList";
import type { Message } from "@/lib/types";

// JSDOM does not implement scrollIntoView; silence the error across all tests.
beforeEach(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});

const userAndAssistant: Message[] = [
  { id: 1, role: "user", content: "Hello", created_at: "2026-03-26T10:00:00Z" },
  { id: 2, role: "assistant", content: "Hi!", created_at: "2026-03-26T10:00:01Z" },
];

describe("MessageList rewind guard", () => {
  it("shows the edit button on user messages when onRewind is provided", () => {
    render(
      <MessageList
        messages={userAndAssistant}
        isLoading={false}
        streamStatus="idle"
        partialText=""
        timings={null}
        onRewind={vi.fn()}
      />
    );
    expect(screen.getByTitle("Edit and resend")).toBeInTheDocument();
  });

  it("hides the edit button when onRewind is undefined", () => {
    render(
      <MessageList
        messages={userAndAssistant}
        isLoading={false}
        streamStatus="idle"
        partialText=""
        timings={null}
        onRewind={undefined}
      />
    );
    expect(screen.queryByTitle("Edit and resend")).not.toBeInTheDocument();
  });

  it("never renders the edit button for assistant-only messages even when onRewind is provided", () => {
    const assistantOnly: Message[] = [
      { id: 1, role: "assistant", content: "Hello", created_at: "2026-03-26T10:00:00Z" },
    ];
    render(
      <MessageList
        messages={assistantOnly}
        isLoading={false}
        streamStatus="idle"
        partialText=""
        timings={null}
        onRewind={vi.fn()}
      />
    );
    expect(screen.queryByTitle("Edit and resend")).not.toBeInTheDocument();
  });

  it("hides the edit button while streaming (simulated by onRewind=undefined)", () => {
    // ChatShell passes onRewind=undefined when isStreaming || isFetching.
    // This test verifies MessageList correctly propagates that contract.
    render(
      <MessageList
        messages={userAndAssistant}
        isLoading={false}
        streamStatus="streaming"
        partialText="partial…"
        timings={null}
        onRewind={undefined}
      />
    );
    expect(screen.queryByTitle("Edit and resend")).not.toBeInTheDocument();
  });
});
