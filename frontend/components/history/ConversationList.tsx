"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useConversationList } from "@/hooks/useConversationList";
import { ConversationListItem } from "./ConversationListItem";

interface ConversationListProps {
  activeConversationId?: string;
}

export function ConversationList({ activeConversationId }: ConversationListProps) {
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;
  const { data, isLoading } = useConversationList(page, PAGE_SIZE);

  if (isLoading) {
    return (
      <div className="space-y-1 p-2">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  }

  const total = data?.total ?? 0;
  const conversations = data?.conversations ?? [];
  const hasPrev = page > 1;
  const hasNext = page * PAGE_SIZE < total;

  return (
    <div className="flex flex-col gap-1 p-2">
      {conversations.length === 0 ? (
        <p className="px-2 py-4 text-center text-xs text-muted-foreground">
          No conversations yet.
        </p>
      ) : (
        conversations.map((c) => (
          <ConversationListItem
            key={c.id}
            conversation={c}
            isActive={c.id === activeConversationId}
          />
        ))
      )}

      {(hasPrev || hasNext) && (
        <div className="mt-2 flex items-center justify-between">
          <Button
            variant="ghost"
            size="icon"
            disabled={!hasPrev}
            onClick={() => setPage((p) => p - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground">
            Page {page}
          </span>
          <Button
            variant="ghost"
            size="icon"
            disabled={!hasNext}
            onClick={() => setPage((p) => p + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
