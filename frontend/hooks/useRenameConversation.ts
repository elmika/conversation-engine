import { useMutation, useQueryClient } from "@tanstack/react-query";
import { renameConversation } from "@/lib/api-client";

export function useRenameConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      renameConversation(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
