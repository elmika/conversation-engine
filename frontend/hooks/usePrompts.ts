import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createPrompt,
  deletePrompt,
  disablePrompt,
  enablePrompt,
  fetchAllPrompts,
  fetchPrompts,
  updatePrompt,
} from "@/lib/api-client";
import type { Prompt, PromptCreateRequest, PromptUpdateRequest, PromptsResponse } from "@/lib/types";

export function usePrompts() {
  return useQuery<PromptsResponse>({
    queryKey: ["prompts"],
    queryFn: fetchPrompts,
    staleTime: 0,
  });
}

export function useAllPrompts() {
  return useQuery<PromptsResponse>({
    queryKey: ["prompts", "all"],
    queryFn: fetchAllPrompts,
    staleTime: 0,
  });
}

export function useCreatePrompt() {
  const queryClient = useQueryClient();
  return useMutation<Prompt, Error, PromptCreateRequest>({
    mutationFn: createPrompt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
    },
  });
}

export function useUpdatePrompt() {
  const queryClient = useQueryClient();
  return useMutation<Prompt, Error, { slug: string; body: PromptUpdateRequest }>({
    mutationFn: ({ slug, body }) => updatePrompt(slug, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
    },
  });
}

export function useDisablePrompt() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: disablePrompt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
    },
  });
}

export function useEnablePrompt() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: enablePrompt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
    },
  });
}

export function useDeletePrompt() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: deletePrompt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
    },
  });
}
