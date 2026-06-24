import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteConversation } from "@/lib/api-client";

export function useDeleteConversation(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteConversation(userId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations", userId] });
    },
  });
}
