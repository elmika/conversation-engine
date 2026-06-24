import { ChatShell } from "@/components/chat/ChatShell";

interface Props {
  params: Promise<{ userId: string }>;
}

export default async function UserChatPage({ params }: Props) {
  const { userId } = await params;
  return <ChatShell userId={userId} />;
}
