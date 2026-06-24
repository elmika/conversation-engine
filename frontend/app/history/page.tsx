import { redirect } from "next/navigation";

/**
 * Legacy route — the canonical URL is now /u/{userId}/history.
 * Redirect to root so the entry point can assign a userId and redirect properly.
 */
export default function HistoryPage() {
  redirect("/");
}
