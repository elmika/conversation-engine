"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePrompts } from "@/hooks/usePrompts";
import { useChatStore } from "@/hooks/useChatStore";
import { Skeleton } from "@/components/ui/skeleton";

export function PromptSelector() {
  const { data, isLoading } = usePrompts();
  const { selectedPromptSlug, setSelectedPromptSlug } = useChatStore();

  if (isLoading) {
    return <Skeleton className="h-9 w-40" />;
  }

  return (
    <Select value={selectedPromptSlug} onValueChange={setSelectedPromptSlug}>
      <SelectTrigger className="w-40">
        <SelectValue placeholder="Select persona" />
      </SelectTrigger>
      <SelectContent>
        {data?.prompts.map((p) => (
          <SelectItem key={p.slug} value={p.slug}>
            {p.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
