"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getAdminToken, setAdminToken, clearAdminToken, ADMIN_TOKEN_EVENT } from "@/lib/adminToken";

/** True if `token` is accepted by the backend right now. */
async function isTokenValid(token: string): Promise<boolean> {
  try {
    const res = await fetch("/api/admin/usage/today", {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Lightweight "paste your admin token once" gate for /admin — no login system,
 * just a sessionStorage-backed token prompt.
 *
 * The token is validated against the backend exactly once per state change,
 * not once per component that happens to be listening:
 * - On mount, if sessionStorage already has one (e.g. a stale token left over
 *   from a previous, since-rotated admin token) — presence alone is never
 *   enough, or the gate would flash real content for a bad token.
 * - On submit, before persisting it.
 * A *clear* elsewhere (api-client's handleAdminResponse/handleAdminVoid, on a
 * 401 from a live admin API call) needs no re-check — "no token" is
 * unambiguous — so the ADMIN_TOKEN_EVENT listener only reacts to that case.
 */
export function AdminTokenGate({ children }: { children: React.ReactNode }) {
  const [authorized, setAuthorized] = useState(false);
  const [ready, setReady] = useState(false);
  const [input, setInput] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const stored = getAdminToken();
    if (!stored) {
      setReady(true);
    } else {
      isTokenValid(stored).then((valid) => {
        if (cancelled) return;
        if (!valid) clearAdminToken();
        setAuthorized(valid);
        setReady(true);
      });
    }

    function handleTokenCleared() {
      if (!getAdminToken()) setAuthorized(false);
    }
    window.addEventListener(ADMIN_TOKEN_EVENT, handleTokenCleared);
    return () => {
      cancelled = true;
      window.removeEventListener(ADMIN_TOKEN_EVENT, handleTokenCleared);
    };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const candidate = input.trim();
    if (!candidate) return;
    setChecking(true);
    setError(null);
    const valid = await isTokenValid(candidate);
    setChecking(false);
    if (!valid) {
      setError("Invalid admin token");
      return;
    }
    setAdminToken(candidate);
    setAuthorized(true);
  }

  // Avoid a flash of the gate (or of stale content) before the first check resolves.
  if (!ready) return null;

  if (authorized) return <>{children}</>;

  return (
    <div className="mx-auto max-w-sm px-4 py-16">
      <h1 className="mb-2 text-lg font-medium">Admin access</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Enter the admin token to continue. It is kept only for this browser tab.
      </p>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div>
          <Label htmlFor="admin-token">Admin token</Label>
          <Input
            id="admin-token"
            type="password"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            autoFocus
            disabled={checking}
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={checking || !input.trim()}>
          {checking ? "Checking…" : "Continue"}
        </Button>
      </form>
    </div>
  );
}
