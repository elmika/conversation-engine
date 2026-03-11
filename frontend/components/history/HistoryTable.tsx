"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { Pencil, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
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
import { useConversationList } from "@/hooks/useConversationList";
import { useRenameConversation } from "@/hooks/useRenameConversation";
import { useDeleteConversation } from "@/hooks/useDeleteConversation";
import { formatDate, truncateId } from "@/lib/utils";
import type { ConversationSummary } from "@/lib/types";

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

function getPageNumbers(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (current <= 4) return [1, 2, 3, 4, 5, "…", total];
  if (current >= total - 3) return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
  return [1, "…", current - 1, current, current + 1, "…", total];
}

interface PaginationProps {
  page: number;
  totalPages: number;
  onChange: (p: number) => void;
}

function Pagination({ page, totalPages, onChange }: PaginationProps) {
  if (totalPages <= 1) return null;
  const pages = getPageNumbers(page, totalPages);
  return (
    <div className="flex items-center justify-center gap-1 pt-4">
      <Button
        variant="ghost"
        size="icon"
        disabled={page === 1}
        onClick={() => onChange(page - 1)}
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>
      {pages.map((p, i) =>
        p === "…" ? (
          <span key={`ellipsis-${i}`} className="px-1 text-muted-foreground text-sm">…</span>
        ) : (
          <Button
            key={p}
            variant={p === page ? "default" : "ghost"}
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => onChange(p as number)}
          >
            {p}
          </Button>
        )
      )}
      <Button
        variant="ghost"
        size="icon"
        disabled={page === totalPages}
        onClick={() => onChange(page + 1)}
      >
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

function HistoryRow({
  conversation,
  striped,
}: {
  conversation: ConversationSummary;
  striped: boolean;
}) {
  const displayName = conversation.name || truncateId(conversation.id);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { mutate: rename } = useRenameConversation();
  const { mutate: remove } = useDeleteConversation();

  function startEditing(e: React.MouseEvent) {
    e.preventDefault();
    setDraft(conversation.name || "");
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  }

  function commit() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== conversation.name) {
      rename({ id: conversation.id, name: trimmed });
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
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={onKeyDown}
            className="w-full rounded border border-input bg-background px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
        ) : (
          <Link
            href={`/chat/${conversation.id}`}
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
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => remove(conversation.id)}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Delete
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

export function HistoryTable() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useConversationList(page, PAGE_SIZE);

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
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">First message</th>
              <th className="px-4 py-3 whitespace-nowrap">Created</th>
              <th className="px-4 py-3 whitespace-nowrap">Last activity</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {conversations.map((c, i) => (
              <HistoryRow key={c.id} conversation={c} striped={i % 2 === 1} />
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
