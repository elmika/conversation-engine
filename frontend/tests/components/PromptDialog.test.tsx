import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../utils";
import { PromptDialog } from "@/components/admin/PromptDialog";

const EXISTING_PROMPT = {
  slug: "default",
  name: "Default",
  system_prompt: "You are a helpful assistant.",
  model: null,
  is_active: true,
};

describe("PromptDialog", () => {
  it("renders create mode with empty fields", () => {
    renderWithProviders(
      <PromptDialog open={true} onOpenChange={vi.fn()} prompt={null} />
    );

    expect(screen.getByText("New Prompt")).toBeInTheDocument();
    expect(screen.getByLabelText("Slug")).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("System Prompt")).toBeInTheDocument();
  });

  it("renders edit mode with slug as readonly badge", () => {
    renderWithProviders(
      <PromptDialog open={true} onOpenChange={vi.fn()} prompt={EXISTING_PROMPT} />
    );

    expect(screen.getByText("Edit Prompt")).toBeInTheDocument();
    // Slug shown as badge text, not an input
    expect(screen.getByText("default")).toBeInTheDocument();
    expect(screen.queryByLabelText("Slug")).not.toBeInTheDocument();
    // Name field pre-filled
    const nameInput = screen.getByLabelText("Name") as HTMLInputElement;
    expect(nameInput.value).toBe("Default");
  });

  it("calls onOpenChange(false) after successful create", async () => {
    const onOpenChange = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(
      <PromptDialog open={true} onOpenChange={onOpenChange} prompt={null} />
    );

    await user.type(screen.getByLabelText("Slug"), "my-new-prompt");
    await user.type(screen.getByLabelText("Name"), "My New Prompt");
    await user.type(screen.getByLabelText("System Prompt"), "You are a new prompt.");
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it("shows error message on duplicate slug (409)", async () => {
    // Override the handler to return 409 for this test
    const { server } = await import("../mocks/server");
    const { http, HttpResponse } = await import("msw");

    server.use(
      http.post("/api/prompts", () =>
        HttpResponse.json({ detail: "Prompt 'existing' already exists" }, { status: 409 })
      )
    );

    const user = userEvent.setup();
    renderWithProviders(
      <PromptDialog open={true} onOpenChange={vi.fn()} prompt={null} />
    );

    await user.type(screen.getByLabelText("Slug"), "existing");
    await user.type(screen.getByLabelText("Name"), "Existing");
    await user.type(screen.getByLabelText("System Prompt"), "System prompt.");
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(screen.getByText("Prompt 'existing' already exists")).toBeInTheDocument();
    });
  });
});
