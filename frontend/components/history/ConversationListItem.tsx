import Link from "next/link";
import { cn, formatDate, truncateId } from "@/lib/utils";
import type { ConversationSummary } from "@/lib/types";

interface ConversationListItemProps {
  conversation: ConversationSummary;
  isActive?: boolean;
}

export function ConversationListItem({
  conversation,
  isActive,
}: ConversationListItemProps) {
  return (
    <Link
      href={`/chat/${conversation.id}`}
      className={cn(
        "block rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent",
        isActive && "bg-accent text-accent-foreground"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs text-muted-foreground">
          {truncateId(conversation.id)}
        </span>
        <span className="text-xs text-muted-foreground">
          {formatDate(conversation.created_at)}
        </span>
      </div>
    </Link>
  );
}
