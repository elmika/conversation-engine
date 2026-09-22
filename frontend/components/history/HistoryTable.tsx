"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { Loader2, Pencil, Trash2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Pagination } from "@/components/Pagination";
import { ConversationListItem } from "@/components/history/ConversationListItem";
import { useConversationList } from "@/hooks/useConversationList";
import { useRenameConversation } from "@/hooks/useRenameConversation";
import { useDeleteConversation } from "@/hooks/useDeleteConversation";
import { formatDate, truncateId } from "@/lib/utils";
import type { ConversationSummary } from "@/lib/types";

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

function HistoryRow({
  userId,
  conversation,
  striped,
}: {
  userId: string;
  conversation: ConversationSummary;
  striped: boolean;
}) {
  const displayName = conversation.name || truncateId(conversation.id);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { mutateAsync: rename, isPending: isRenaming } = useRenameConversation(userId);
  const { mutateAsync: remove, isPending: isRemoving } = useDeleteConversation(userId);

  function startEditing(e: React.MouseEvent) {
    e.preventDefault();
    setDraft(conversation.name || "");
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  }

  async function commit() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== conversation.name) {
      await rename({ id: conversation.id, name: trimmed });
    }
    setEditing(false);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") commit();
    if (e.key === "Escape") setEditing(false);
  }

  return (
    <tr
      className={`
        border-b transition-colors hover:bg-accent/60
        ${striped ? "bg-muted/30" : "bg-background"}
      `}
    >
      {/* Name */}
      <td className="px-4 py-3 font-medium max-w-[200px]">
        {editing ? (
          <input
            ref={inputRef}
            autoFocus
            value={draft}
            disabled={isRenaming}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={onKeyDown}
            className="w-full rounded border border-input bg-background px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
          />
        ) : (
          <Link
            href={`/u/${userId}/chat/${conversation.id}`}
            className="block truncate hover:underline"
            title={conversation.name || undefined}
          >
            {displayName}
          </Link>
        )}
      </td>

      {/* First message preview */}
      <td className="px-4 py-3 text-sm text-muted-foreground max-w-[300px]">
        <span className="block truncate" title={conversation.first_message || undefined}>
          {conversation.first_message || <span className="italic">—</span>}
        </span>
      </td>

      {/* Created */}
      <td className="px-4 py-3 text-sm text-muted-foreground whitespace-nowrap">
        {formatDate(conversation.created_at)}
      </td>

      {/* Last activity */}
      <td className="px-4 py-3 text-sm text-muted-foreground whitespace-nowrap">
        {conversation.last_activity ? formatDate(conversation.last_activity) : "—"}
      </td>

      {/* Actions */}
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={startEditing}
            className="text-muted-foreground hover:text-foreground transition-colors"
            title="Rename"
          >
            <Pencil className="h-4 w-4" />
          </button>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <button
                className="text-muted-foreground hover:text-destructive transition-colors"
                title="Delete"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete conversation?</AlertDialogTitle>
                <AlertDialogDescription>
                  &ldquo;{displayName}&rdquo; and all its messages will be permanently deleted.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel disabled={isRemoving}>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => remove(conversation.id)}
                  disabled={isRemoving}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {isRemoving ? (
                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Deleting…</>
                  ) : "Delete"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

const PAGE_SIZE = 20;

interface HistoryTableProps {
  userId: string;
}

export function HistoryTable({ userId }: HistoryTableProps) {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useConversationList(userId, page, PAGE_SIZE);

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
      {/* Dense table — comfortably fits Name/First message/Created/Last activity
          columns on tablet+ widths. Below md, a narrow screen can't fit all five
          columns without clipping, so a stacked card list (mirroring the sidebar's
          ConversationListItem) takes over instead. */}
      <div className="hidden rounded-lg border overflow-hidden md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">First message</th>
              <th className="px-4 py-3 whitespace-nowrap">Created</th>
              <th className="px-4 py-3 whitespace-nowrap">Last activity</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {conversations.map((c, i) => (
              <HistoryRow key={c.id} userId={userId} conversation={c} striped={i % 2 === 1} />
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-1 md:hidden">
        {conversations.map((c) => (
          <ConversationListItem key={c.id} userId={userId} conversation={c} showDelete />
        ))}
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
