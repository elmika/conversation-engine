"use client";

/**
 * Root entry point.
 *
 * Reads (or generates) a stable UUID for this learner from localStorage, checks
 * whether they've already recorded consent, and either redirects straight to
 * their personal chat space at /u/{userId}/chat or shows the consent gate
 * first — see docs/roadmap.md's "GDPR: no consent gate..." entry.
 *
 * UUID-in-URL is the only identity mechanism — no auth, no sign-in. Bookmarking
 * the resulting URL is how learners return to their session.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getOrCreateUserId } from "@/lib/user-id";
import { fetchConsentStatus, recordConsent } from "@/lib/api-client";
import { ConsentScreen } from "@/components/ConsentScreen";

export default function Home() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [needsConsent, setNeedsConsent] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = getOrCreateUserId();
    setUserId(id);

    fetchConsentStatus(id)
      .then((status) => {
        if (status.consented) {
          router.replace(`/u/${id}/chat`);
        } else {
          setNeedsConsent(true);
        }
      })
      .catch(() => {
        // Can't confirm consent was already recorded — fail closed and show
        // the gate rather than risk letting an unconsented learner through
        // on a transient network/server error.
        setNeedsConsent(true);
      });
  }, [router]);

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

  if (needsConsent && userId) {
    return (
      <ConsentScreen onContinue={handleContinue} isSubmitting={isSubmitting} error={error} />
    );
  }

  return null;
}
