import { useQuery } from "@tanstack/react-query";
import { fetchSessionSummary } from "@/lib/api-client";

export function useSessionSummary(userId: string, conversationId: string | null | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["session-summary", userId, conversationId],
    queryFn: () => fetchSessionSummary(userId, conversationId!),
    enabled: Boolean(conversationId && enabled),
    staleTime: Infinity, // summary doesn't change after session ends
  });
}
