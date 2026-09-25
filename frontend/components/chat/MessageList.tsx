"use client";

import { useEffect, useRef } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { MessageBubble } from "./MessageBubble";
import { StreamingMessage } from "./StreamingMessage";
import type { Message } from "@/lib/types";
import type { StreamStatus } from "@/hooks/useStreamingChat";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  streamStatus: StreamStatus;
  partialText: string;
  promptSlug?: string | null;
  onRewind?: (messageId: number, newContent: string) => void;
}

const NEAR_BOTTOM_THRESHOLD = 80; // px

export function MessageList({
  messages,
  isLoading,
  streamStatus,
  partialText,
  promptSlug,
  onRewind,
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  // When false, the user has taken control of the scroll and we stop
  // auto-following the streamed text until they return to the bottom.
  const stickToBottom = useRef(true);
  // Once the *current* streaming reply has grown taller than the visible
  // area, stop chasing the tail on every chunk — the reader is very likely
  // reading from the top of a still-growing message, and repeatedly forcing
  // the view down to the newest token yanks that text out from under them
  // (reported: "the text moves up... then goes down again and hides the
  // part I'm trying to read"). Resets for each new reply so a short answer
  // still snaps into view immediately; re-armed if the reader scrolls back
  // to the bottom themselves (see onScroll below), signaling they now want
  // to follow along live.
  const hasOverflowedThisMessage = useRef(false);
  const wasStreaming = useRef(false);
  const isStreaming = streamStatus === "connecting" || streamStatus === "streaming";

  const isNearBottom = () => {
    const el = scrollRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_THRESHOLD;
  };

  // Any upward user gesture (wheel, trackpad, touch, keyboard) immediately
  // hands control to the reader; returning to the bottom re-engages following.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const releaseOnUpwardIntent = (deltaY: number) => {
      if (deltaY < 0) stickToBottom.current = false;
    };
    const onWheel = (e: WheelEvent) => releaseOnUpwardIntent(e.deltaY);
    const onKeyDown = (e: KeyboardEvent) => {
      if (["ArrowUp", "PageUp", "Home"].includes(e.key)) {
        stickToBottom.current = false;
      }
    };
    // Touch: compare successive positions to detect an upward drag.
    let lastTouchY = 0;
    const onTouchStart = (e: TouchEvent) => {
      lastTouchY = e.touches[0]?.clientY ?? 0;
    };
    const onTouchMove = (e: TouchEvent) => {
      const y = e.touches[0]?.clientY ?? 0;
      // Finger moving down drags content down → reveals earlier text (scroll up).
      if (y > lastTouchY) stickToBottom.current = false;
      lastTouchY = y;
    };
    // Re-engage following the moment the user is back at the bottom — also
    // clears the overflow freeze, since scrolling to the bottom themselves
    // is a deliberate signal they want to watch the rest stream in live.
    const onScroll = () => {
      if (isNearBottom()) {
        stickToBottom.current = true;
        hasOverflowedThisMessage.current = false;
      }
    };

    el.addEventListener("wheel", onWheel, { passive: true });
    el.addEventListener("keydown", onKeyDown);
    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchmove", onTouchMove, { passive: true });
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("keydown", onKeyDown);
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchmove", onTouchMove);
      el.removeEventListener("scroll", onScroll);
    };
  }, []);

  // New user message: always scroll to bottom and re-engage following. An
  // instant jump (not smooth) — see the streaming-scroll rule below; a smooth
  // scroll here can still be mid-animation when the first chunk arrives,
  // fighting that effect's own instant jump.
  useEffect(() => {
    const last = messages[messages.length - 1];
    if (last?.role === "user") {
      stickToBottom.current = true;
      hasOverflowedThisMessage.current = false;
      bottomRef.current?.scrollIntoView({ behavior: "auto" });
    }
  }, [messages]);

  // A new assistant reply starting gets a fresh chance to feel snappy before
  // we decide whether it's grown past the viewport.
  useEffect(() => {
    if (isStreaming && !wasStreaming.current) {
      hasOverflowedThisMessage.current = false;
    }
    wasStreaming.current = isStreaming;
  }, [isStreaming]);

  // Streaming chunks: follow only while sticking to the bottom AND the
  // current reply hasn't yet outgrown the visible area. Use an instant jump
  // (not smooth) so the animation never competes with the reader's scroll.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && el.scrollHeight > el.clientHeight) {
      hasOverflowedThisMessage.current = true;
    }
    if (stickToBottom.current && !hasOverflowedThisMessage.current) {
      bottomRef.current?.scrollIntoView({ behavior: "auto" });
    }
  }, [partialText]);

  if (isLoading && messages.length === 0) {
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

        {isStreaming && <StreamingMessage partialText={partialText} promptSlug={promptSlug} />}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
