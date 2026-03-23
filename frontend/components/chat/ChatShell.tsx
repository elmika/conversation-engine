"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { CornerDownLeft, PanelLeft, Plus, SquarePen, StopCircle } from "lucide-react";
import { ChatInput } from "./ChatInput";
import { MessageList } from "./MessageList";
import { ModelSelector } from "./ModelSelector";
import { PromptSelector } from "./PromptSelector";
import { ConversationList } from "@/components/history/ConversationList";
import { useChatStore } from "@/hooks/useChatStore";
import { useConversation } from "@/hooks/useConversation";
import { useStreamingChat } from "@/hooks/useStreamingChat";
import { cn } from "@/lib/utils";
import type { Message } from "@/lib/types";

interface ChatShellProps {
  conversationId?: string;
}

export function ChatShell({ conversationId }: ChatShellProps) {
  const router = useRouter();
  const { isSidebarOpen, toggleSidebar, selectedPromptSlug, selectedModelSlug, enterToSend, toggleEnterToSend } = useChatStore();
  const { data, isLoading } = useConversation(conversationId ?? null);
  const { status, partialText, timings, model, errorMessage, sendMessage, rewindAndStream, cancel, reset, conversationId: streamedConversationId } =
    useStreamingChat();

  // After the first turn the hook captures the server-assigned ID; use it for
  // follow-up turns when there is no URL-based conversationId.
  const activeConversationId = conversationId ?? streamedConversationId ?? undefined;

  const [localMessages, setLocalMessages] = useState<Message[]>([]);
  const prevStatusRef = useRef(status);

  // Sync server messages into local state on initial load and after each refetch
  useEffect(() => {
    if (data?.messages) {
      setLocalMessages(data.messages);
    }
  }, [data?.messages]);

  // When the stream finishes, append the assistant reply to localMessages immediately
  // so there is no visible gap before the query refetch arrives with server data
  useEffect(() => {
    if (prevStatusRef.current !== "done" && status === "done" && partialText) {
      setLocalMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant" as const,
          content: partialText,
          created_at: new Date().toISOString(),
        },
      ]);
    }
    prevStatusRef.current = status;
  }, [status, partialText]);

  const isStreaming = status === "connecting" || status === "streaming";

  const handleNewConversation = () => {
    reset();
    setLocalMessages([]);
    router.push("/chat");
  };

  const handleRewind = (messageId: number, newContent: string) => {
    if (!activeConversationId) return;

    // Optimistically truncate local messages at the rewound message
    setLocalMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === messageId);
      const kept = idx >= 0 ? prev.slice(0, idx) : prev;
      return [
        ...kept,
        {
          id: Date.now(),
          role: "user" as const,
          content: newContent,
          created_at: new Date().toISOString(),
        },
      ];
    });

    rewindAndStream(activeConversationId, messageId, newContent, selectedPromptSlug);
  };

  const handleSend = (text: string) => {
    // Optimistically show the user message immediately
    setLocalMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        role: "user" as const,
        content: text,
        created_at: new Date().toISOString(),
      },
    ]);

    sendMessage(
      { messages: [{ role: "user", content: text }], prompt_slug: selectedPromptSlug, model_slug: selectedModelSlug },
      activeConversationId
    );
  };

  return (
    <div className="flex h-full overflow-hidden bg-background">
      {/* Sidebar */}
      <aside
        className={cn(
          "flex flex-col border-r bg-muted/30 transition-all duration-200",
          isSidebarOpen ? "w-64" : "w-0 overflow-hidden"
        )}
      >
        <div className="flex items-center justify-between p-3">
          <span className="text-sm font-semibold">History</span>
          <Link href="/chat">
            <Button variant="ghost" size="icon" title="New conversation">
              <Plus className="h-4 w-4" />
            </Button>
          </Link>
        </div>
        <Separator />
        <div className="flex-1 overflow-y-auto">
          <ConversationList activeConversationId={conversationId} />
        </div>
      </aside>

      {/* Main chat area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center gap-2 border-b px-4 py-2">
          <Button variant="ghost" size="icon" onClick={toggleSidebar} title="Toggle sidebar">
            <PanelLeft className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={handleNewConversation} title="New conversation">
            <SquarePen className="h-4 w-4" />
          </Button>
          <PromptSelector />
          <ModelSelector />
          <div className="ml-auto">
            <Button
              variant={enterToSend ? "secondary" : "ghost"}
              size="sm"
              onClick={toggleEnterToSend}
              title={enterToSend ? "Enter sends message — click to switch to Ctrl+Enter" : "Ctrl+Enter sends message — click to switch to Enter"}
              className="gap-1.5 text-xs text-muted-foreground"
            >
              <CornerDownLeft className="h-3.5 w-3.5" />
              {enterToSend ? "Enter to send" : "Ctrl+Enter to send"}
            </Button>
          </div>
        </header>

        {/* Messages */}
        <MessageList
          messages={localMessages}
          isLoading={isLoading}
          streamStatus={status}
          partialText={partialText}
          timings={timings}
          model={model}
          onRewind={activeConversationId ? handleRewind : undefined}
        />

        {/* Error banner */}
        {status === "error" && errorMessage && (
          <div className="mx-4 mb-2 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {errorMessage}
          </div>
        )}

        {/* Input */}
        <div className="border-t p-4">
          {isStreaming ? (
            <div className="flex justify-center">
              <Button variant="outline" size="sm" onClick={cancel} className="gap-2">
                <StopCircle className="h-4 w-4" />
                Stop
              </Button>
            </div>
          ) : (
            <ChatInput onSend={handleSend} disabled={false} enterToSend={enterToSend} />
          )}
        </div>
      </div>
    </div>
  );
}
