import { useQuery } from "@tanstack/react-query";
import { fetchConversationMessages } from "@/lib/api-client";
import type { MessagesResponse } from "@/lib/types";

export function useConversation(userId: string, conversationId: string | null) {
  return useQuery<MessagesResponse>({
    queryKey: ["messages", userId, conversationId],
    queryFn: () => fetchConversationMessages(userId, conversationId!),
    enabled: conversationId !== null,
  });
}
