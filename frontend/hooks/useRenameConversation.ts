import { useMutation, useQueryClient } from "@tanstack/react-query";
import { renameConversation } from "@/lib/api-client";

export function useRenameConversation(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      renameConversation(userId, id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations", userId] });
    },
  });
}
