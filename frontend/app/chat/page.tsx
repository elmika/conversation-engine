"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getOrCreateUserId } from "@/lib/user-id";

/**
 * Legacy route — the canonical URL is now /u/{userId}/chat.
 */
export default function ChatPage() {
  const router = useRouter();

  useEffect(() => {
    const userId = getOrCreateUserId();
    router.replace(`/u/${userId}/chat`);
  }, [router]);

  return null;
}
