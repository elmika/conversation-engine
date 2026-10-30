import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const pathname = vi.hoisted(() => ({ current: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.current }));

const getOrCreateUserId = vi.hoisted(() => vi.fn(() => "stored-user"));
vi.mock("@/lib/user-id", () => ({ getOrCreateUserId }));

import { NavBar } from "@/components/NavBar";
import { BottomNav } from "@/components/BottomNav";

describe("learner nav vs admin", () => {
  beforeEach(() => {
    getOrCreateUserId.mockClear();
    sessionStorage.clear();
  });

  it.each(["/admin", "/admin/conversations"])(
    "renders nothing on %s and never creates a learner id",
    (path) => {
      pathname.current = path;
      const { container } = render(
        <>
          <NavBar />
          <BottomNav />
        </>,
      );

      expect(container).toBeEmptyDOMElement();
      expect(getOrCreateUserId).not.toHaveBeenCalled();
    },
  );

  it("shows Chat and History for a learner, and no Admin tab even with an admin token", () => {
    pathname.current = "/u/learner-1/chat";
    sessionStorage.setItem("skillforge_admin_token", "x");
    render(<NavBar />);

    expect(screen.getByRole("link", { name: /chat/i })).toHaveAttribute("href", "/u/learner-1/chat");
    expect(screen.getByRole("link", { name: /history/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /admin/i })).not.toBeInTheDocument();
  });

  it("does not treat a learner path that merely starts with 'admin' as admin", () => {
    pathname.current = "/administrator";
    render(<NavBar />);

    expect(screen.getByRole("link", { name: /chat/i })).toBeInTheDocument();
  });
});
