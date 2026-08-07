import { describe, it, expect } from "vitest";
import {
  conversationToMarkdown,
  conversationFilename,
} from "@/lib/export-conversation";
import type { Message, SessionSummary } from "@/lib/types";

const MESSAGES: Message[] = [
  { id: 1, role: "assistant", content: "Welcome back! Let's start Module One.", created_at: "2026-06-25T10:00:00Z" },
  { id: 2, role: "user", content: "Sounds good.", created_at: "2026-06-25T10:01:00Z" },
];

describe("conversationToMarkdown", () => {
  it("emits YAML frontmatter with conversation metadata", () => {
    const md = conversationToMarkdown(
      {
        conversationId: "abc-123",
        name: "course-session-init",
        promptSlug: "course-session-init",
        createdAt: "2026-06-25T10:00:00Z",
        endedAt: null,
        messages: MESSAGES,
      },
      "2026-06-25T12:00:00Z",
    );
    expect(md.startsWith("---\n")).toBe(true);
    expect(md).toContain('conversation_id: "abc-123"');
    expect(md).toContain('course_prompt: "course-session-init"');
    expect(md).toContain("ended_at: null");
    expect(md).toContain('exported_at: "2026-06-25T12:00:00Z"');
    expect(md).toContain("message_count: 2");
  });

  it("renders each turn with a human role label and timestamp", () => {
    const md = conversationToMarkdown({
      conversationId: "abc-123",
      messages: MESSAGES,
    });
    expect(md).toContain("### Tutor · 2026-06-25T10:00:00Z");
    expect(md).toContain("Welcome back! Let's start Module One.");
    expect(md).toContain("### Learner · 2026-06-25T10:01:00Z");
    expect(md).toContain("Sounds good.");
  });

  it("appends the session summary when the session was wrapped", () => {
    const summary: SessionSummary = {
      course_name: "TypeScript Mentor",
      modules: [
        { title: "Basics", status: "done" },
        { title: "Generics", status: "current" },
      ],
      next_step: "Practice generic constraints.",
    };
    const md = conversationToMarkdown({
      conversationId: "abc-123",
      endedAt: "2026-06-25T10:30:00Z",
      messages: MESSAGES,
      summary,
    });
    expect(md).toContain("## Session summary");
    expect(md).toContain("**Course:** TypeScript Mentor");
    expect(md).toContain("- ✓ Basics");
    expect(md).toContain("- → Generics");
    expect(md).toContain("**Where to pick up next time:** Practice generic constraints.");
  });

  it("omits the summary section for an unwrapped conversation", () => {
    const md = conversationToMarkdown({
      conversationId: "abc-123",
      messages: MESSAGES,
      summary: null,
    });
    expect(md).not.toContain("## Session summary");
  });
});

describe("conversationFilename", () => {
  it("builds a filesystem-friendly name from slug + short id + date", () => {
    const name = conversationFilename(
      { conversationId: "2c1f8a3e-1111-2222-3333-444455556666", name: "TypeScript Mentor!" },
      new Date("2026-06-25T12:00:00Z"),
    );
    expect(name).toBe("conversation-typescript-mentor-2c1f8a3e-20260625.md");
  });

  it("falls back to a generic slug when there is no name", () => {
    const name = conversationFilename(
      { conversationId: "2c1f8a3e-aaaa", name: null },
      new Date("2026-06-25T12:00:00Z"),
    );
    expect(name).toBe("conversation-conversation-2c1f8a3e-20260625.md");
  });
});
