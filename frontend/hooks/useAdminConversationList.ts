import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAdminConversations } from "@/lib/api-client";
import type { ConversationListResponse } from "@/lib/types";

export function useAdminConversationList(page = 1, pageSize = 20) {
  const queryClient = useQueryClient();

  const query = useQuery<ConversationListResponse>({
    queryKey: ["admin-conversations", page, pageSize],
    queryFn: () => fetchAdminConversations(page, pageSize),
  });

  // Prefetch next page if there are more results
  const total = query.data?.total ?? 0;
  const hasNextPage = page * pageSize < total;
  if (hasNextPage) {
    queryClient.prefetchQuery({
      queryKey: ["admin-conversations", page + 1, pageSize],
      queryFn: () => fetchAdminConversations(page + 1, pageSize),
    });
  }

  return query;
}
