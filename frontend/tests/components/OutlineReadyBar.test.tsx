import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OutlineReadyBar } from "@/components/chat/OutlineReadyBar";

describe("OutlineReadyBar", () => {
  it("calls onStart when Let's start is clicked", async () => {
    const onStart = vi.fn();
    render(<OutlineReadyBar onStart={onStart} isStarting={false} />);

    await userEvent.click(screen.getByRole("button", { name: /let's start/i }));

    expect(onStart).toHaveBeenCalledOnce();
  });

  it("tells the learner they can still change the outline", () => {
    render(<OutlineReadyBar onStart={vi.fn()} isStarting={false} />);

    expect(screen.getByText(/reply below to change it/i)).toBeInTheDocument();
  });

  it("disables the button and shows progress while setup completes", () => {
    render(<OutlineReadyBar onStart={vi.fn()} isStarting={true} />);

    const button = screen.getByRole("button", { name: /setting up/i });
    expect(button).toBeDisabled();
  });
});
