import { describe, it, expect, beforeEach } from "vitest";
import { getOrCreateUserId, getStoredUserId, setCurrentUserId } from "@/lib/user-id";

const KEY = "learning-platform-user-id";

beforeEach(() => {
  localStorage.clear();
});

describe("getOrCreateUserId", () => {
  it("case 1: first-ever visit mints a UUID and stores it", () => {
    expect(localStorage.getItem(KEY)).toBeNull();

    const id = getOrCreateUserId();

    expect(id).toMatch(/^[0-9a-f-]{36}$/);
    expect(localStorage.getItem(KEY)).toBe(id);
  });

  it("case 2: returning visit retrieves the existing UUID without minting a new one", () => {
    const existing = "11111111-1111-1111-1111-111111111111";
    localStorage.setItem(KEY, existing);

    const id = getOrCreateUserId();

    expect(id).toBe(existing);
    expect(localStorage.getItem(KEY)).toBe(existing);
  });
});

describe("getStoredUserId", () => {
  it("returns null when nothing has ever been stored — never mints one", () => {
    expect(getStoredUserId()).toBeNull();
    // Unlike getOrCreateUserId, reading must not have side effects.
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it("returns the stored UUID when one exists", () => {
    localStorage.setItem(KEY, "22222222-2222-2222-2222-222222222222");
    expect(getStoredUserId()).toBe("22222222-2222-2222-2222-222222222222");
  });
});

describe("setCurrentUserId", () => {
  it("overwrites whatever was previously stored", () => {
    localStorage.setItem(KEY, "old-id");
    setCurrentUserId("new-id");
    expect(localStorage.getItem(KEY)).toBe("new-id");
  });
});
