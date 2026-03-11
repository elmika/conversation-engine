import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteConversation } from "@/lib/api-client";

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
