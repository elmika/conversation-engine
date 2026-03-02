import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../utils";
import { ConversationList } from "@/components/history/ConversationList";

describe("ConversationList", () => {
  it("renders skeleton while loading", () => {
    const { container } = renderWithProviders(<ConversationList />);
    // Skeletons use animate-pulse before data resolves
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows conversation links after data loads", async () => {
    renderWithProviders(<ConversationList />);

    // MSW fixture has two conversations — wait for links to appear
    await waitFor(() => {
      const links = screen.getAllByRole("link");
      expect(links.length).toBeGreaterThanOrEqual(2);
    });

    const links = screen.getAllByRole("link");
    const hrefs = links.map((l) => l.getAttribute("href"));
    expect(hrefs).toContain("/chat/test-conv-id-1");
    expect(hrefs).toContain("/chat/test-conv-id-2");
  });

  it("highlights the active conversation link", async () => {
    renderWithProviders(
      <ConversationList activeConversationId="test-conv-id-1" />
    );

    await waitFor(() => {
      const activeLink = screen
        .getAllByRole("link")
        .find((l) => l.getAttribute("href") === "/chat/test-conv-id-1");
      expect(activeLink?.className).toContain("bg-accent");
    });
  });
});
