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

interface PromptSelectorProps {
  /** When set, the conversation's prompt is locked — show it as a static label. */
  lockedSlug?: string | null;
}

export function PromptSelector({ lockedSlug }: PromptSelectorProps) {
  const { data, isLoading } = usePrompts();
  const { selectedPromptSlug, setSelectedPromptSlug } = useChatStore();

  if (isLoading) {
    return <Skeleton className="h-9 w-40" />;
  }

  if (lockedSlug) {
    const prompt = data?.prompts.find((p) => p.slug === lockedSlug);
    return (
      <div className="flex h-9 w-40 items-center rounded-md border border-input bg-muted/50 px-3 text-sm text-muted-foreground">
        {prompt?.name ?? lockedSlug}
      </div>
    );
  }

  return (
    <Select value={selectedPromptSlug} onValueChange={setSelectedPromptSlug}>
      <SelectTrigger className="w-40">
        <SelectValue placeholder="Select course" />
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
