import { useQuery } from "@tanstack/react-query";
import { fetchConversationMessages } from "@/lib/api-client";
import type { MessagesResponse } from "@/lib/types";

export function useConversation(conversationId: string | null) {
  return useQuery<MessagesResponse>({
    queryKey: ["messages", conversationId],
    queryFn: () => fetchConversationMessages(conversationId!),
    enabled: conversationId !== null,
  });
}
