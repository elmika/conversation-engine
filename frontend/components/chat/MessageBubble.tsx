"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { CodeBlock } from "./CodeBlock";
import type { MessageRole } from "@/lib/types";

interface MessageBubbleProps {
  role: MessageRole;
  content: string;
  messageId?: number;
  onRewind?: (messageId: number, newContent: string) => void;
}

const markdownComponents = {
  pre({ children }: { children?: React.ReactNode }) {
    return <>{children}</>;
  },
  code({ className, children }: { className?: string; children?: React.ReactNode }) {
    const match = /language-(\w+)/.exec(className || "");
    const codeString = String(children).replace(/\n$/, "");
    const isBlock = Boolean(match) || codeString.includes("\n");

    if (isBlock) {
      return <CodeBlock language={match?.[1] ?? ""} code={codeString} />;
    }
    return (
      <code className="bg-zinc-100 dark:bg-zinc-700 rounded px-1 py-0.5 text-xs font-mono">
        {children}
      </code>
    );
  },
};

export function MessageBubble({ role, content, messageId, onRewind }: MessageBubbleProps) {
  const isUser = role === "user";
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleCopyMessage = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const startEditing = () => {
    setDraft(content);
    setEditing(true);
    setTimeout(() => {
      const el = textareaRef.current;
      if (el) {
        el.focus();
        el.setSelectionRange(el.value.length, el.value.length);
      }
    }, 0);
  };

  const cancelEditing = () => setEditing(false);

  const commitRewind = () => {
    const trimmed = draft.trim();
    if (trimmed && messageId !== undefined && onRewind) {
      onRewind(messageId, trimmed);
    }
    setEditing(false);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      commitRewind();
    }
    if (e.key === "Escape") {
      cancelEditing();
    }
  };

  if (isUser && editing) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] w-full space-y-2">
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            rows={Math.min(10, draft.split("\n").length + 1)}
            className="w-full rounded-xl border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={cancelEditing}>
              Cancel
            </Button>
            <Button size="sm" onClick={commitRewind} disabled={!draft.trim()}>
              Resend
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "relative group max-w-[80%] rounded-2xl px-4 py-2 text-sm",
          isUser ? "bg-blue-500 text-white" : "bg-muted text-foreground"
        )}
      >
        {isUser ? (
          <>
            <p className="whitespace-pre-wrap">{content}</p>
            {onRewind && messageId !== undefined && (
              <button
                onClick={startEditing}
                className="absolute -left-7 top-1/2 -translate-y-1/2 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity hover:text-foreground"
                title="Edit and resend"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            )}
          </>
        ) : (
          <>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{content}</ReactMarkdown>
            </div>
            <button
              onClick={handleCopyMessage}
              className="absolute bottom-2 right-3 text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity hover:text-foreground"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
