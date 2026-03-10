import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchConversations } from "@/lib/api-client";
import type { ConversationListResponse } from "@/lib/types";

export function useConversationList(page = 1, pageSize = 20) {
  const queryClient = useQueryClient();

  const query = useQuery<ConversationListResponse>({
    queryKey: ["conversations", page, pageSize],
    queryFn: () => fetchConversations(page, pageSize),
  });

  // Prefetch next page if there are more results
  const total = query.data?.total ?? 0;
  const hasNextPage = page * pageSize < total;
  if (hasNextPage) {
    queryClient.prefetchQuery({
      queryKey: ["conversations", page + 1, pageSize],
      queryFn: () => fetchConversations(page + 1, pageSize),
    });
  }

  return query;
}
