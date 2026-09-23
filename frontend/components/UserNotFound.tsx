import Link from "next/link";
import { Button } from "@/components/ui/button";

/**
 * Shown by UserIdGate when a /u/{userId}/... URL names a UUID that's neither
 * this browser's own stored id nor a known learner (no profile, no
 * conversations) — most likely a mistyped or stale link. Never adopted into
 * localStorage; "Go to my session" always returns to whatever this browser's
 * real stored session is (or mints a fresh one if none exists).
 */
export function UserNotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-md rounded-lg border bg-card p-6 text-center shadow-sm">
        <h1 className="text-lg font-semibold">We couldn&apos;t find that session</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          This link doesn&apos;t match a known learner. If someone sent it to you, double-check
          it was copied in full.
        </p>
        <Button asChild className="mt-5 w-full">
          <Link href="/">Go to my session</Link>
        </Button>
      </div>
    </div>
  );
}
