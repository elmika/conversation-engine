"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pagination } from "@/components/Pagination";
import { useAdminConversationList } from "@/hooks/useAdminConversationList";
import { fetchAdminConversationMessages } from "@/lib/api-client";
import { formatDate, truncateId } from "@/lib/utils";
import type { ConversationSummary } from "@/lib/types";

// ---------------------------------------------------------------------------
// Transcript (expand-in-place)
// ---------------------------------------------------------------------------

function Transcript({ conversationId }: { conversationId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin-conversation-messages", conversationId],
    queryFn: () => fetchAdminConversationMessages(conversationId),
  });

  if (isLoading) {
    return <p className="py-4 text-sm text-muted-foreground">Loading transcript…</p>;
  }
  if (isError || !data) {
    return <p className="py-4 text-sm text-destructive">Failed to load transcript.</p>;
  }

  return (
    <div className="max-h-96 space-y-3 overflow-y-auto rounded-md border bg-background p-4">
      {data.messages.map((m) => (
        <div key={m.id} className="text-sm">
          <span className="font-semibold capitalize">{m.role}</span>
          <span className="ml-2 text-xs text-muted-foreground">{formatDate(m.created_at)}</span>
          <p className="whitespace-pre-wrap text-foreground">{m.content}</p>
        </div>
      ))}
      {data.messages.length === 0 && (
        <p className="text-sm text-muted-foreground">No messages in this conversation.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

function ConversationRow({
  conversation,
  striped,
  expanded,
  onToggle,
}: {
  conversation: ConversationSummary;
  striped: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  const displayName = conversation.name || truncateId(conversation.id);

  return (
    <>
      <tr
        onClick={onToggle}
        className={`
          cursor-pointer border-b transition-colors hover:bg-accent/60
          ${striped ? "bg-muted/30" : "bg-background"}
        `}
      >
        <td className="px-4 py-3 text-sm text-muted-foreground whitespace-nowrap">
          {truncateId(conversation.user_id || "")}
        </td>
        <td className="px-4 py-3 font-medium max-w-[200px]">
          <span className="block truncate" title={conversation.name || undefined}>
            {displayName}
          </span>
        </td>
        <td className="px-4 py-3 text-sm text-muted-foreground max-w-[300px]">
          <span className="block truncate" title={conversation.first_message || undefined}>
            {conversation.first_message || <span className="italic">—</span>}
          </span>
        </td>
        <td className="px-4 py-3 text-sm text-muted-foreground whitespace-nowrap">
          {formatDate(conversation.created_at)}
        </td>
        <td className="px-4 py-3 text-sm text-muted-foreground whitespace-nowrap">
          {conversation.last_activity ? formatDate(conversation.last_activity) : "—"}
        </td>
      </tr>
      {expanded && (
        <tr className={striped ? "bg-muted/30" : "bg-background"}>
          <td colSpan={5} className="px-4 pb-4">
            <Transcript conversationId={conversation.id} />
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

const PAGE_SIZE = 20;

export function AdminConversationsTable() {
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { data, isLoading } = useAdminConversationList(page, PAGE_SIZE);

  const conversations = data?.conversations ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-12 animate-pulse rounded bg-muted" />
        ))}
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <p className="py-12 text-center text-muted-foreground">No conversations yet.</p>
    );
  }

  return (
    <div>
      <div className="rounded-lg border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">First message</th>
              <th className="px-4 py-3 whitespace-nowrap">Created</th>
              <th className="px-4 py-3 whitespace-nowrap">Last activity</th>
            </tr>
          </thead>
          <tbody>
            {conversations.map((c, i) => (
              <ConversationRow
                key={c.id}
                conversation={c}
                striped={i % 2 === 1}
                expanded={expandedId === c.id}
                onToggle={() => setExpandedId(expandedId === c.id ? null : c.id)}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between pt-4 text-sm text-muted-foreground">
        <span>
          {total} conversation{total !== 1 ? "s" : ""} — page {page} of {totalPages}
        </span>
        <Pagination page={page} totalPages={totalPages} onChange={setPage} />
      </div>
    </div>
  );
}
