"use client";

/**
 * Legacy route — the canonical URL is now /u/{userId}/chat/{conversationId}.
 *
 * The userId lives in localStorage (client-side only), so we resolve it here and
 * redirect while PRESERVING the conversationId, rather than dropping it by
 * bouncing through the root entry point.
 */

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getOrCreateUserId } from "@/lib/user-id";

export default function ConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const router = useRouter();
  const { conversationId } = use(params);

  useEffect(() => {
    const userId = getOrCreateUserId();
    router.replace(`/u/${userId}/chat/${conversationId}`);
  }, [router, conversationId]);

  return null;
}
