"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { CornerDownLeft, Loader2, LogOut, PanelLeft, Plus, SquarePen, StopCircle } from "lucide-react";
import { ChatInput } from "./ChatInput";
import { MessageList } from "./MessageList";
import { ModelSelector } from "./ModelSelector";
import { PromptSelector } from "./PromptSelector";
import { SessionSummaryCard } from "./SessionSummaryCard";
import { ConversationList } from "@/components/history/ConversationList";
import { useChatStore } from "@/hooks/useChatStore";
import { useConversation } from "@/hooks/useConversation";
import { useSessionSummary } from "@/hooks/useSessionSummary";
import { useStreamingChat } from "@/hooks/useStreamingChat";
import { cn } from "@/lib/utils";
import { endSession } from "@/lib/api-client";
import type { Message } from "@/lib/types";

interface ChatShellProps {
  conversationId?: string;
}

export function ChatShell({ conversationId }: ChatShellProps) {
  const router = useRouter();
  const { isSidebarOpen, toggleSidebar, selectedPromptSlug, selectedModelSlug, enterToSend, toggleEnterToSend } = useChatStore();
  const { status, partialText, timings, model, errorMessage, sendMessage, initSession, rewindAndStream, cancel, reset, conversationId: streamedConversationId } =
    useStreamingChat();

  // After the first turn the hook captures the server-assigned ID; use it for
  // follow-up turns when there is no URL-based conversationId.
  const activeConversationId = conversationId ?? streamedConversationId ?? undefined;

  // Use activeConversationId so that new conversations (no URL param yet) also
  // get a query refetch once the server assigns an ID after the first turn.
  const { data, isLoading, isFetching } = useConversation(activeConversationId ?? null);

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

  // Auto-fire AI opening message when starting a new (no-URL) conversation.
  // Also re-fires when status returns to "idle" after handleNewConversation resets the ref.
  const initFiredRef = useRef(false);
  useEffect(() => {
    if (!conversationId && !initFiredRef.current && status === "idle") {
      initFiredRef.current = true;
      initSession(selectedPromptSlug, selectedModelSlug, (activeId) => {
        router.push(`/chat/${activeId}`);
      });
    }
  }, [conversationId, status]); // eslint-disable-line react-hooks/exhaustive-deps

  const isStreaming = status === "connecting" || status === "streaming";
  const isEnded = Boolean(data?.ended_at);

  const { data: sessionSummary } = useSessionSummary(activeConversationId, isEnded);
  const [summaryVisible, setSummaryVisible] = useState(true);

  const [endSessionError, setEndSessionError] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const { mutate: endSessionMutate, isPending: isEndingSession } = useMutation({
    mutationFn: () => endSession(activeConversationId!),
    onMutate: () => setEndSessionError(null),
    onSuccess: () => {
      setSummaryVisible(true);
      queryClient.invalidateQueries({ queryKey: ["session-summary", activeConversationId] });
      queryClient.invalidateQueries({ queryKey: ["messages", activeConversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (err: Error) => {
      setEndSessionError(err.message ?? "Failed to end session. Please try again.");
    },
  });

  const handleNewConversation = () => {
    initFiredRef.current = false; // allow init to re-fire after reset()
    reset();                       // sets status → "idle", triggering the effect above
    setLocalMessages([]);
    setSummaryVisible(true);
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
          <Button variant="ghost" size="icon" title="New conversation" onClick={handleNewConversation}>
            <Plus className="h-4 w-4" />
          </Button>
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
          <div className="ml-auto flex items-center gap-2">
            {activeConversationId && !isStreaming && !isEnded && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => endSessionMutate()}
                disabled={isEndingSession}
                className="gap-1.5 text-xs"
                title="End this session and update progress"
              >
                {isEndingSession ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <LogOut className="h-3.5 w-3.5" />
                )}
                {isEndingSession ? "Ending…" : "End Session"}
              </Button>
            )}
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
          onRewind={activeConversationId && !isStreaming && !isFetching ? handleRewind : undefined}
        />

        {/* Error banner */}
        {status === "error" && errorMessage && (
          <div className="mx-4 mb-2 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {errorMessage}
          </div>
        )}
        {endSessionError && (
          <div className="mx-4 mb-2 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            End session failed: {endSessionError}
          </div>
        )}

        {/* Input */}
        <div className="border-t p-4">
          {isEnded ? (
            sessionSummary && summaryVisible ? (
              <SessionSummaryCard
                summary={sessionSummary}
                onStartNextSession={handleNewConversation}
                onClose={() => setSummaryVisible(false)}
              />
            ) : (
              <div className="flex items-center justify-between rounded-md border border-muted bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                <span>Session ended.</span>
                <div className="flex items-center gap-2">
                  {sessionSummary && (
                    <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setSummaryVisible(true)}>
                      View summary
                    </Button>
                  )}
                  <Button variant="outline" size="sm" className="h-7 text-xs" onClick={handleNewConversation}>
                    Start new session
                  </Button>
                </div>
              </div>
            )
          ) : isStreaming ? (
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
