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
