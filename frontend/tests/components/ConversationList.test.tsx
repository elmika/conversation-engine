import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../utils";
import { ConversationList } from "@/components/history/ConversationList";

const TEST_USER = "test-user-id";

describe("ConversationList", () => {
  it("renders skeleton while loading", () => {
    const { container } = renderWithProviders(<ConversationList userId={TEST_USER} />);
    // Skeletons use animate-pulse before data resolves
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows conversation links after data loads", async () => {
    renderWithProviders(<ConversationList userId={TEST_USER} />);

    // MSW fixture has two conversations — wait for links to appear
    await waitFor(() => {
      const links = screen.getAllByRole("link");
      expect(links.length).toBeGreaterThanOrEqual(2);
    });

    const links = screen.getAllByRole("link");
    const hrefs = links.map((l) => l.getAttribute("href"));
    expect(hrefs).toContain(`/u/${TEST_USER}/chat/test-conv-id-1`);
    expect(hrefs).toContain(`/u/${TEST_USER}/chat/test-conv-id-2`);
  });

  it("highlights the active conversation link", async () => {
    renderWithProviders(
      <ConversationList userId={TEST_USER} activeConversationId="test-conv-id-1" />
    );

    await waitFor(() => {
      const activeLink = screen
        .getAllByRole("link")
        .find((l) => l.getAttribute("href") === `/u/${TEST_USER}/chat/test-conv-id-1`);
      expect(activeLink?.className).toContain("bg-accent");
    });
  });
});
