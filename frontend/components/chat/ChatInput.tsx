"use client";

import { useState, useRef, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { SendHorizonal, Square } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  enterToSend?: boolean;
  // While a reply streams, the box stays mounted (same height, keeps focus, so the reader can
  // type their next message) and the send button becomes Stop. Swapping the whole box for a
  // Stop button resized the message list at the end of every reply and hid its last lines.
  isStreaming?: boolean;
  onStop?: () => void;
}

export function ChatInput({
  onSend,
  disabled = false,
  enterToSend = true,
  isStreaming = false,
  onStop,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const text = value.trim();
    if (!text || disabled || isStreaming) return;
    onSend(text);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (enterToSend) {
      // Enter sends, Shift+Enter inserts newline
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    } else {
      // Ctrl+Enter / Cmd+Enter sends, Enter inserts newline
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleSend();
      }
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  };

  const hint = enterToSend
    ? "Enter to send — Shift+Enter for new line"
    : "Ctrl+Enter to send — Enter for new line";

  return (
    <div className="space-y-1">
      <div className="flex items-end gap-2 rounded-xl border bg-background p-2 shadow-sm">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          disabled={disabled}
          placeholder="Type a message…"
          rows={1}
          className={cn(
            "flex-1 resize-none bg-transparent text-sm leading-relaxed outline-none placeholder:text-muted-foreground",
            "max-h-40 overflow-y-auto",
            disabled && "opacity-50 cursor-not-allowed"
          )}
        />
        {isStreaming && onStop ? (
          <Button size="icon" variant="outline" onClick={onStop} aria-label="Stop generating" title="Stop">
            <Square className="h-4 w-4" />
          </Button>
        ) : (
          <Button
            size="icon"
            onClick={handleSend}
            disabled={disabled || isStreaming || !value.trim()}
            aria-label="Send message"
          >
            <SendHorizonal className="h-4 w-4" />
          </Button>
        )}
      </div>
      <p className="px-1 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}
