"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

interface ConsentScreenProps {
  onContinue: () => void;
  isSubmitting: boolean;
  error?: string | null;
}

/**
 * Minimal GDPR consent gate shown before a fresh learner ever reaches chat.
 *
 * Copy is final (reviewed with Mika 2026-09-17) — not a draft to improve on.
 * See docs/roadmap.md's "GDPR: no consent gate..." entry for the full spec,
 * including two decisions already closed: no nickname prompt instead of a
 * real name, and "anonymized" is disclosed as limited-strength on purpose.
 */
export function ConsentScreen({ onContinue, isSubmitting, error }: ConsentScreenProps) {
  const [checked, setChecked] = useState(false);
  const checkboxId = useId();

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-lg rounded-lg border bg-card p-6 shadow-sm">
        <p className="text-sm leading-relaxed text-foreground">
          Before we start: SkillForge is a live pilot, not a finished product. To personalise
          your course we&apos;ll ask your name, role, and what you want to learn — and everything
          you write in a session is saved so the tutor can pick up where you left off next time.
          As the person running this pilot, I can see your name and messages to build and improve
          the product; nobody else does. Your messages are sent to OpenAI and Anthropic to
          generate the tutor&apos;s replies, same as any AI chat tool. Nothing is sold or shared beyond that.
          This pilot is provided as-is, with no guarantee of availability, and I may end it at any
          time without needing to justify why. It&apos;s expected to run for around two weeks —
          enough time to complete one course. After the pilot, I may keep an anonymized version of
          session content to improve the product. You can ask for your data to be deleted at any
          time — mikael.baron@squaredpoint.com.
        </p>

        <label htmlFor={checkboxId} className="mt-5 flex items-start gap-2.5 text-sm">
          <input
            id={checkboxId}
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 rounded border-input"
          />
          <span>I understand and agree to this.</span>
        </label>

        {error && (
          <p className="mt-3 text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        <Button
          className="mt-5 w-full"
          disabled={!checked || isSubmitting}
          onClick={onContinue}
        >
          {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Continue
        </Button>
      </div>
    </div>
  );
}
