"use client";

/**
 * Force-starts a brand-new learner identity, discarding whatever UUID is
 * currently stored in this browser — for testing/demos where you want a
 * fresh learner without manually clearing localStorage.
 *
 * Unlike "/", this never reuses an existing stored UUID. Consent is always
 * unrecorded for a freshly-minted id, so this skips the consent-status
 * check "/" does and shows the consent screen directly. Once the freshly
 * minted id is stored, UserIdGate (app/u/[userId]/layout.tsx) trusts it
 * immediately on arrival at /u/{id}/chat — it matches what's already in
 * localStorage, so there's no existence check and no chance of landing on
 * the "not found" screen.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { mintNewUserId } from "@/lib/user-id";
import { recordConsent } from "@/lib/api-client";
import { ConsentScreen } from "@/components/ConsentScreen";

export default function NewUserPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setUserId(mintNewUserId());
  }, []);

  async function handleContinue() {
    if (!userId) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await recordConsent(userId);
      router.replace(`/u/${userId}/chat`);
    } catch {
      setError("Couldn't save your consent. Please try again.");
      setIsSubmitting(false);
    }
  }

  if (!userId) return null;

  return <ConsentScreen onContinue={handleContinue} isSubmitting={isSubmitting} error={error} />;
}
