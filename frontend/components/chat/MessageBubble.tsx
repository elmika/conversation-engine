"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import { CodeBlock } from "./CodeBlock";
import type { MessageRole } from "@/lib/types";

interface MessageBubbleProps {
  role: MessageRole;
  content: string;
}

const markdownComponents = {
  pre({ children }: { children?: React.ReactNode }) {
    // Let CodeBlock handle its own wrapper — suppress default <pre>
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

export function MessageBubble({ role, content }: MessageBubbleProps) {
  const isUser = role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopyMessage = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "relative group max-w-[80%] rounded-2xl px-4 py-2 text-sm",
          isUser ? "bg-blue-500 text-white" : "bg-muted text-foreground"
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown components={markdownComponents}>{content}</ReactMarkdown>
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
