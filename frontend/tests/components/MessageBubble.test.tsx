import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageBubble } from "@/components/chat/MessageBubble";

describe("MessageBubble", () => {
  it("renders user message right-aligned", () => {
    const { container } = render(
      <MessageBubble role="user" content="Hello there" />
    );
    expect(screen.getByText("Hello there")).toBeInTheDocument();
    // Outer wrapper should have justify-end
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("justify-end");
  });

  it("renders assistant message left-aligned", () => {
    const { container } = render(
      <MessageBubble role="assistant" content="Hi!" />
    );
    expect(screen.getByText("Hi!")).toBeInTheDocument();
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("justify-start");
  });

  it("renders markdown in assistant messages", () => {
    render(
      <MessageBubble role="assistant" content="**bold text**" />
    );
    expect(screen.getByText("bold text").tagName).toBe("STRONG");
  });

  it("renders user content as plain text (no markdown processing)", () => {
    render(<MessageBubble role="user" content="**not bold**" />);
    expect(screen.getByText("**not bold**")).toBeInTheDocument();
  });
});
