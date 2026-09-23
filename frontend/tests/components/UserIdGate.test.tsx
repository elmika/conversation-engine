import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { renderWithProviders } from "../utils";
import { UserIdGate } from "@/components/UserIdGate";

const KEY = "learning-platform-user-id";
const OWN_ID = "own-user-id";
const OTHER_ID = "other-user-id";

beforeEach(() => {
  localStorage.clear();
});

function mockExistence(userId: string, { hasProfile = false, conversationCount = 0 }) {
  server.use(
    http.get(`/api/u/${userId}/status`, () =>
      HttpResponse.json({ has_profile: hasProfile })
    ),
    http.get(`/api/u/${userId}/conversations`, () =>
      HttpResponse.json({
        conversations: [],
        total: conversationCount,
        page: 1,
        page_size: 1,
      })
    )
  );
}

describe("UserIdGate", () => {
  it("case 1/2: userId matching (or absent from) storage is trusted without an existence check", async () => {
    // Nothing stored yet — this is the "first visit under this id" path.
    renderWithProviders(
      <UserIdGate userId={OWN_ID}>
        <div>chat content</div>
      </UserIdGate>
    );

    await waitFor(() => expect(screen.getByText("chat content")).toBeInTheDocument());
    expect(localStorage.getItem(KEY)).toBe(OWN_ID);
  });

  it("case 3: a different but known userId is adopted and children render", async () => {
    localStorage.setItem(KEY, OWN_ID);
    mockExistence(OTHER_ID, { hasProfile: true });

    renderWithProviders(
      <UserIdGate userId={OTHER_ID}>
        <div>chat content</div>
      </UserIdGate>
    );

    await waitFor(() => expect(screen.getByText("chat content")).toBeInTheDocument());
    expect(localStorage.getItem(KEY)).toBe(OTHER_ID);
  });

  it("case 3b: known via conversation history alone (no profile yet) is also adopted", async () => {
    localStorage.setItem(KEY, OWN_ID);
    mockExistence(OTHER_ID, { conversationCount: 3 });

    renderWithProviders(
      <UserIdGate userId={OTHER_ID}>
        <div>chat content</div>
      </UserIdGate>
    );

    await waitFor(() => expect(screen.getByText("chat content")).toBeInTheDocument());
    expect(localStorage.getItem(KEY)).toBe(OTHER_ID);
  });

  it("case 4: a different, unknown userId is not adopted and shows UserNotFound instead of children", async () => {
    localStorage.setItem(KEY, OWN_ID);
    mockExistence(OTHER_ID, {}); // no profile, no conversations

    renderWithProviders(
      <UserIdGate userId={OTHER_ID}>
        <div>chat content</div>
      </UserIdGate>
    );

    await waitFor(() =>
      expect(screen.getByText(/couldn.t find that session/i)).toBeInTheDocument()
    );
    expect(screen.queryByText("chat content")).not.toBeInTheDocument();
    // localStorage must be untouched — still the original, not OTHER_ID.
    expect(localStorage.getItem(KEY)).toBe(OWN_ID);
  });

  it("fails safe: a network error while checking is treated as not-found, never adopted", async () => {
    localStorage.setItem(KEY, OWN_ID);
    server.use(
      http.get(`/api/u/${OTHER_ID}/status`, () => HttpResponse.error()),
      http.get(`/api/u/${OTHER_ID}/conversations`, () => HttpResponse.error())
    );

    renderWithProviders(
      <UserIdGate userId={OTHER_ID}>
        <div>chat content</div>
      </UserIdGate>
    );

    await waitFor(() =>
      expect(screen.getByText(/couldn.t find that session/i)).toBeInTheDocument()
    );
    expect(localStorage.getItem(KEY)).toBe(OWN_ID);
  });
});
