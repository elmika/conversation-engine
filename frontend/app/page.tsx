"use client";

/**
 * Root entry point.
 *
 * Reads (or generates) a stable UUID for this learner from localStorage, then
 * redirects to their personal chat space at /u/{userId}/chat.
 *
 * UUID-in-URL is the only identity mechanism — no auth, no sign-in. Bookmarking
 * the resulting URL is how learners return to their session.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";

const USER_ID_KEY = "learning-platform-user-id";

function getOrCreateUserId(): string {
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const userId = getOrCreateUserId();
    router.replace(`/u/${userId}/chat`);
  }, [router]);

  return null;
}
