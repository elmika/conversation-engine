"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getOrCreateUserId } from "@/lib/user-id";

/**
 * Legacy route — the canonical URL is now /u/{userId}/history.
 * Redirects straight there, never through /u/{userId}/chat (which
 * auto-starts a session on load) — see docs/roadmap.md items 2/5.
 */
export default function HistoryPage() {
  const router = useRouter();

  useEffect(() => {
    const userId = getOrCreateUserId();
    router.replace(`/u/${userId}/history`);
  }, [router]);

  return null;
}
