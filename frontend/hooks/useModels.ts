import { useQuery } from "@tanstack/react-query";
import { fetchModels } from "@/lib/api-client";
import type { ModelsResponse } from "@/lib/types";

export function useModels() {
  return useQuery<ModelsResponse>({
    queryKey: ["models"],
    queryFn: fetchModels,
    staleTime: Infinity,
  });
}
