"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useModels } from "@/hooks/useModels";
import { useChatStore } from "@/hooks/useChatStore";
import { Skeleton } from "@/components/ui/skeleton";

export function ModelSelector() {
  const { data, isLoading } = useModels();
  const { selectedModelSlug, setSelectedModelSlug } = useChatStore();

  if (isLoading) {
    return <Skeleton className="h-9 w-44" />;
  }

  return (
    <Select
      value={selectedModelSlug ?? ""}
      onValueChange={(value) => setSelectedModelSlug(value || null)}
    >
      <SelectTrigger className="w-44">
        <SelectValue placeholder="Default (auto)" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="">Default (auto)</SelectItem>
        {data?.models.map((m) => (
          <SelectItem key={m.slug} value={m.slug} title={m.description}>
            {m.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
