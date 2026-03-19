"use client";

import { useEffect, useRef } from "react";
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
  onRewind?: (messageId: number, newContent: string) => void;
}

const NEAR_BOTTOM_THRESHOLD = 80; // px

export function MessageList({
  messages,
  isLoading,
  streamStatus,
  partialText,
  timings,
  onRewind,
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);
  const isStreaming = streamStatus === "connecting" || streamStatus === "streaming";

  const isNearBottom = () => {
    const el = scrollRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_THRESHOLD;
  };

  // Detect manual scroll up
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      userScrolledUp.current = !isNearBottom();
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // New user message: always scroll to bottom and reset the lock
  useEffect(() => {
    const last = messages[messages.length - 1];
    if (last?.role === "user") {
      userScrolledUp.current = false;
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Streaming chunks: scroll only if the user hasn't scrolled up
  useEffect(() => {
    if (!userScrolledUp.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [partialText]);

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
    <div ref={scrollRef} className="flex-1 overflow-y-auto">
      <div className="flex flex-col gap-3 p-4">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            role={msg.role}
            content={msg.content}
            messageId={msg.id}
            onRewind={msg.role === "user" ? onRewind : undefined}
          />
        ))}

        {isStreaming && <StreamingMessage partialText={partialText} />}

        {streamStatus === "done" && timings && (
          <div className="flex justify-start pl-1">
            <TimingsBadge timings={timings} />
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
