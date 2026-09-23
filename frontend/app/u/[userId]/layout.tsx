import { UserIdGate } from "@/components/UserIdGate";

interface Props {
  children: React.ReactNode;
  params: Promise<{ userId: string }>;
}

/**
 * Shared by every /u/{userId}/... page (chat, chat/[conversationId],
 * history, and the bare redirect page). Gates rendering behind an identity
 * check and adopts this userId into localStorage once trusted — see
 * UserIdGate.
 */
export default async function UserLayout({ children, params }: Props) {
  const { userId } = await params;
  return <UserIdGate userId={userId}>{children}</UserIdGate>;
}
