/**
 * Learner identity helper.
 *
 * UUID-in-URL is the only identity mechanism — no auth, no sign-in. The UUID is
 * stored in localStorage so a learner returning without a URL (or via a legacy
 * route) is mapped back to the same personal space.
 */

const USER_ID_KEY = "learning-platform-user-id";

/** Read the learner's stable UUID from localStorage, creating one if absent. */
export function getOrCreateUserId(): string {
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

/** Read the learner's stored UUID, or null if none has ever been set — never
 * creates one (unlike getOrCreateUserId). Used by UserIdGate to tell "this is
 * already my own id" apart from "I'm visiting a different id". */
export function getStoredUserId(): string | null {
  return localStorage.getItem(USER_ID_KEY);
}

/**
 * Adopt userId as this browser's current identity. Called by UserIdGate,
 * only after confirming userId is either already this browser's own id or a
 * known/existing one — so visiting another learner's URL (e.g. an
 * admin/support person following a direct link) makes that the browser's
 * session going forward. Without this, localStorage keeps pointing at
 * whatever was previously stored, and the next redirect through "/" (e.g.
 * the consent gate) silently falls back to it instead of staying on the
 * userId actually being viewed.
 */
export function setCurrentUserId(userId: string): void {
  localStorage.setItem(USER_ID_KEY, userId);
}
