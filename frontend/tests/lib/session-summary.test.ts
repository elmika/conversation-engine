import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { fetchSessionSummary } from "@/lib/api-client";

const SUMMARY_URL = "*/api/u/:userId/conversations/:conversationId/summary";

describe("fetchSessionSummary", () => {
  it("returns the saved summary", async () => {
    const summary = { course_name: "Pandas", modules: [], next_step: null };
    server.use(http.get(SUMMARY_URL, () => HttpResponse.json(summary)));

    await expect(fetchSessionSummary("u1", "c1")).resolves.toEqual(summary);
  });

  it("returns null when no summary was saved for the conversation (404)", async () => {
    server.use(
      http.get(SUMMARY_URL, () =>
        HttpResponse.json({ detail: "No summary was saved for this conversation" }, { status: 404 }),
      ),
    );

    await expect(fetchSessionSummary("u1", "c1")).resolves.toBeNull();
  });

  it("still throws on other errors", async () => {
    server.use(http.get(SUMMARY_URL, () => HttpResponse.json({ detail: "boom" }, { status: 500 })));

    await expect(fetchSessionSummary("u1", "c1")).rejects.toThrow();
  });
});
