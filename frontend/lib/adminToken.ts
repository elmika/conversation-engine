/**
 * Admin bearer token storage — sessionStorage only (not localStorage), so the
 * token never silently persists across browser restarts or a shared machine.
 *
 * Since sessionStorage writes in the same tab don't fire the native `storage`
 * event, we dispatch a custom window event so other mounted components (the
 * token gate) can react immediately when the token is set or cleared.
 */

const STORAGE_KEY = "skillforge_admin_token";
export const ADMIN_TOKEN_EVENT = "admin-token-changed";

export function getAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setAdminToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, token);
  } catch {
    // sessionStorage unavailable (private mode, etc.) — the gate will just re-prompt.
  }
  window.dispatchEvent(new Event(ADMIN_TOKEN_EVENT));
}

export function clearAdminToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // no-op
  }
  window.dispatchEvent(new Event(ADMIN_TOKEN_EVENT));
}
