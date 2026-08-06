import { redirect } from "next/navigation";

interface Props {
  params: Promise<{ userId: string }>;
}

/**
 * Bare /u/{userId} (no /chat or /history suffix) — redirect to the canonical
 * default view. The userId is already in the URL, so no client-side
 * localStorage lookup is needed here.
 */
export default async function UserRootPage({ params }: Props) {
  const { userId } = await params;
  redirect(`/u/${userId}/chat`);
}
