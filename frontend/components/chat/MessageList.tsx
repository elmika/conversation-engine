"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { MessageBubble } from "./MessageBubble";
import { StreamingMessage } from "./StreamingMessage";
import { TimingsBadge } from "./TimingsBadge";
import type { Message, Timings } from "@/lib/types";
import type { StreamStatus } from "@/hooks/useStreamingChat";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  streamStatus: StreamStatus;
  partialText: string;
  timings: Timings | null;
  /** The user message that was just sent, shown optimistically while streaming. */
  pendingUserMessage?: string;
}

export function MessageList({
  messages,
  isLoading,
  streamStatus,
  partialText,
  timings,
  pendingUserMessage,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const isStreaming = streamStatus === "connecting" || streamStatus === "streaming";

  // Auto-scroll to bottom whenever messages or partial text change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, partialText]);

  if (isLoading) {
    return (
      <div className="flex-1 space-y-4 p-4">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-12 w-3/4" />
        ))}
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1">
      <div className="flex flex-col gap-3 p-4">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} role={msg.role} content={msg.content} />
        ))}

        {/* Optimistic user message shown before streaming begins */}
        {pendingUserMessage && isStreaming && messages.length === 0 && (
          <MessageBubble role="user" content={pendingUserMessage} />
        )}

        {/* Streaming assistant response */}
        {isStreaming && (
          <StreamingMessage partialText={partialText} />
        )}

        {/* Timings shown after stream completes */}
        {streamStatus === "done" && timings && (
          <div className="flex justify-start pl-1">
            <TimingsBadge timings={timings} />
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
