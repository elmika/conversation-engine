import { useQuery } from "@tanstack/react-query";
import { fetchPrompts } from "@/lib/api-client";
import type { PromptsResponse } from "@/lib/types";

export function usePrompts() {
  return useQuery<PromptsResponse>({
    queryKey: ["prompts"],
    queryFn: fetchPrompts,
    staleTime: Infinity,
  });
}
