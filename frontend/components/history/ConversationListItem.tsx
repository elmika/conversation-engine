"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { Pencil } from "lucide-react";
import { cn, formatDate, truncateId } from "@/lib/utils";
import { useRenameConversation } from "@/hooks/useRenameConversation";
import type { ConversationSummary } from "@/lib/types";

interface ConversationListItemProps {
  conversation: ConversationSummary;
  isActive?: boolean;
}

export function ConversationListItem({
  conversation,
  isActive,
}: ConversationListItemProps) {
  const displayName = conversation.name || truncateId(conversation.id);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { mutate: rename } = useRenameConversation();

  function startEditing(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
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

  const sharedClassName = cn(
    "group flex items-center justify-between gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent",
    isActive && "bg-accent text-accent-foreground"
  );

  const content = (
    <>
      {editing ? (
        <input
          ref={inputRef}
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={onKeyDown}
          onClick={(e) => e.preventDefault()}
          className="min-w-0 flex-1 rounded border border-input bg-background px-1 py-0.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        />
      ) : (
        <span
          className="min-w-0 flex-1 truncate font-medium"
          title={conversation.name || undefined}
        >
          {displayName}
        </span>
      )}

      <div className="flex shrink-0 items-center gap-1">
        {!editing && (
          <button
            onClick={startEditing}
            className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
            title="Rename"
          >
            <Pencil className="h-3 w-3" />
          </button>
        )}
        <span className="text-xs text-muted-foreground">
          {formatDate(conversation.created_at)}
        </span>
      </div>
    </>
  );

  if (editing) {
    return <div className={sharedClassName}>{content}</div>;
  }

  return (
    <Link href={`/chat/${conversation.id}`} className={sharedClassName}>
      {content}
    </Link>
  );
}
