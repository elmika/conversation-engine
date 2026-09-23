"use client";

import { useEffect, useState } from "react";
import { getStoredUserId, setCurrentUserId } from "@/lib/user-id";
import { fetchUserStatus, fetchConversations } from "@/lib/api-client";
import { UserNotFound } from "@/components/UserNotFound";

type GateState = "checking" | "trusted" | "not-found";

/**
 * Gates every /u/{userId}/... page (chat, chat/[conversationId], history,
 * the bare redirect) behind an identity check, and adopts userId into
 * localStorage as this browser's current session once trusted.
 *
 * Two ways to be trusted, no existence check needed:
 * - userId matches what's already stored (the common case: this is already
 *   my own session).
 * - Nothing is stored yet (first-ever visit under this browser, however it
 *   was reached) — nothing to protect, so trust it.
 *
 * Otherwise userId names a *different* id than the one already stored —
 * e.g. following a direct link to another learner's session, or a typo.
 * Only adopt it (and render children) if it's a known learner (has a
 * profile, or at least one conversation); otherwise show UserNotFound
 * without ever writing to localStorage or rendering children, so a typo
 * can't silently orphan the browser from its real session or spin up a
 * phantom learner under a bogus id.
 *
 * Fails safe: a network error while checking is treated as "not found" —
 * never adopt/trust on uncertain information.
 */
export function UserIdGate({
  userId,
  children,
}: {
  userId: string;
  children: React.ReactNode;
}) {
  const [state, setState] = useState<GateState>("checking");

  useEffect(() => {
    let cancelled = false;
    setState("checking");

    async function resolve() {
      const stored = getStoredUserId();
      if (!stored || stored === userId) {
        setCurrentUserId(userId);
        if (!cancelled) setState("trusted");
        return;
      }

      try {
        const [status, conversations] = await Promise.all([
          fetchUserStatus(userId),
          fetchConversations(userId, 1, 1),
        ]);
        if (cancelled) return;
        const isKnownUser = status.has_profile || conversations.total > 0;
        if (isKnownUser) {
          setCurrentUserId(userId);
          setState("trusted");
        } else {
          setState("not-found");
        }
      } catch {
        if (!cancelled) setState("not-found");
      }
    }

    resolve();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (state === "checking") return null;
  if (state === "not-found") return <UserNotFound />;
  return <>{children}</>;
}
