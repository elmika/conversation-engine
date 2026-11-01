import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatInput } from "@/components/chat/ChatInput";

describe("ChatInput", () => {
  it("calls onSend with the typed message when Enter is pressed", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "Hello{Enter}");

    expect(onSend).toHaveBeenCalledOnce();
    expect(onSend).toHaveBeenCalledWith("Hello");
  });

  it("clears the input after sending", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "Hello{Enter}");

    expect((textarea as HTMLTextAreaElement).value).toBe("");
  });

  it("inserts a newline on Shift+Enter without sending", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "line1{Shift>}{Enter}{/Shift}line2");

    expect(onSend).not.toHaveBeenCalled();
    expect((textarea as HTMLTextAreaElement).value).toContain("line1");
    expect((textarea as HTMLTextAreaElement).value).toContain("line2");
  });

  it("send button calls onSend when clicked", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    await userEvent.type(screen.getByRole("textbox"), "Hello");
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSend).toHaveBeenCalledWith("Hello");
  });

  it("disables textarea and send button when disabled prop is true", () => {
    render(<ChatInput onSend={vi.fn()} disabled />);

    expect(screen.getByRole("textbox")).toBeDisabled();
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("does not call onSend for whitespace-only input", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    await userEvent.type(screen.getByRole("textbox"), "   {Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("while streaming: stays typeable, Enter doesn't send, and the button stops", async () => {
    const onSend = vi.fn();
    const onStop = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming onStop={onStop} />);

    const textarea = screen.getByRole("textbox");
    expect(textarea).not.toBeDisabled();
    await userEvent.type(textarea, "next question{Enter}");
    expect(onSend).not.toHaveBeenCalled();
    expect((textarea as HTMLTextAreaElement).value).toBe("next question");

    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(onStop).toHaveBeenCalledOnce();
  });

  it("keeps what was typed during streaming and sends it once the reply is done", async () => {
    const onSend = vi.fn();
    const { rerender } = render(<ChatInput onSend={onSend} isStreaming onStop={vi.fn()} />);
    await userEvent.type(screen.getByRole("textbox"), "next question");

    rerender(<ChatInput onSend={onSend} isStreaming={false} onStop={vi.fn()} />);
    await userEvent.type(screen.getByRole("textbox"), "{Enter}");

    expect(onSend).toHaveBeenCalledWith("next question");
  });
});
