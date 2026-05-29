import { ChatShell } from "@/components/chat/ChatShell";

interface Props {
  params: Promise<{ userId: string; conversationId: string }>;
}

export default async function UserConversationPage({ params }: Props) {
  const { userId, conversationId } = await params;
  return <ChatShell userId={userId} conversationId={conversationId} />;
}
