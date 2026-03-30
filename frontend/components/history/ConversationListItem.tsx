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
import { cn, formatDate, truncateId } from "@/lib/utils";
import { useRenameConversation } from "@/hooks/useRenameConversation";
import { useDeleteConversation } from "@/hooks/useDeleteConversation";
import type { ConversationSummary } from "@/lib/types";

interface ConversationListItemProps {
  conversation: ConversationSummary;
  isActive?: boolean;
  showDelete?: boolean;
}

export function ConversationListItem({
  conversation,
  isActive,
  showDelete = false,
}: ConversationListItemProps) {
  const displayName = conversation.name || truncateId(conversation.id);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { mutateAsync: rename, isPending: isRenaming } = useRenameConversation();
  const { mutateAsync: remove, isPending: isRemoving } = useDeleteConversation();

  function startEditing(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
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

  const sharedClassName = cn(
    "group flex items-center justify-between gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent",
    isActive && "bg-accent text-accent-foreground"
  );

  const isSessionActive = !conversation.ended_at;

  const actions = (
    <div className="flex shrink-0 items-center gap-1">
      {isSessionActive && (
        <span className="flex items-center gap-1 rounded-full bg-green-500/15 px-1.5 py-0.5 text-[10px] font-medium text-green-600 dark:text-green-400">
          <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
          Active
        </span>
      )}
      {!editing && (
        <button
          onClick={startEditing}
          className={cn(
            "transition-opacity text-muted-foreground hover:text-foreground",
            showDelete ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          )}
          title="Rename"
        >
          <Pencil className="h-3 w-3" />
        </button>
      )}
      {!editing && showDelete && (
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <button
              onClick={(e) => e.stopPropagation()}
              className="text-muted-foreground hover:text-destructive"
              title="Delete"
            >
              <Trash2 className="h-3 w-3" />
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
      )}
      <span className="text-xs text-muted-foreground">
        {formatDate(conversation.created_at)}
      </span>
    </div>
  );

  const nameSlot = editing ? (
    <input
      ref={inputRef}
      autoFocus
      value={draft}
      disabled={isRenaming}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={onKeyDown}
      onClick={(e) => e.preventDefault()}
      className="min-w-0 flex-1 rounded border border-input bg-background px-1 py-0.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
    />
  ) : (
    <span className="min-w-0 flex-1 truncate font-medium" title={conversation.name || undefined}>
      {displayName}
    </span>
  );

  if (editing) {
    return (
      <div className={sharedClassName}>
        {nameSlot}
        {actions}
      </div>
    );
  }

  return (
    <Link href={`/chat/${conversation.id}`} className={sharedClassName}>
      {nameSlot}
      {actions}
    </Link>
  );
}
