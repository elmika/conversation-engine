"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { CornerDownLeft, Download, Loader2, LogOut, PanelLeft, Plus, Sparkles, SquarePen, StopCircle } from "lucide-react";
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
import { completeSetup, endSession, fetchUserStatus } from "@/lib/api-client";
import {
  conversationToMarkdown,
  conversationFilename,
  downloadTextFile,
} from "@/lib/export-conversation";
import type { Message } from "@/lib/types";

interface ChatShellProps {
  userId: string;
  conversationId?: string;
}

export function ChatShell({ userId, conversationId }: ChatShellProps) {
  const router = useRouter();
  const { isSidebarOpen, toggleSidebar, selectedPromptSlug, selectedModelSlug, enterToSend, toggleEnterToSend } = useChatStore();
  const { status, partialText, timings, model, errorMessage, sendMessage, initSession, rewindAndStream, cancel, reset, conversationId: streamedConversationId } =
    useStreamingChat(userId);

  // After the first turn the hook captures the server-assigned ID; use it for
  // follow-up turns when there is no URL-based conversationId.
  const activeConversationId = conversationId ?? streamedConversationId ?? undefined;

  // Use activeConversationId so that new conversations (no URL param yet) also
  // get a query refetch once the server assigns an ID after the first turn.
  const { data, isLoading, isFetching } = useConversation(userId, activeConversationId ?? null);

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

  // Check whether this user has a profile (sections files exist).
  // initSession requires {{course}} / {{user}} section files — only fire it for
  // users who have completed setup. New users see a blank chat until setup runs.
  const { data: userStatus } = useQuery({
    queryKey: ["user-status", userId],
    queryFn: () => fetchUserStatus(userId),
    staleTime: 60_000,
  });
  const hasProfile = userStatus?.has_profile ?? false;

  // While the user-status query is unresolved, hasProfile defaults false, which
  // would resolve effectivePromptSlug to the setup prompt. Sending in that window
  // on a fresh chat would lock a brand-new conversation to setup — wrong for a
  // profiled user. Inside an existing conversation the prompt is already locked
  // server-side, so sending is always safe there; only gate new-conversation creation.
  const awaitingUserStatus = userStatus === undefined && !activeConversationId;

  // Users without a profile run through the setup flow: a guided conversation
  // that collects their profile + goal and proposes a course outline.
  // Once setup completes, hasProfile flips true and the user picks from the
  // regular course list.
  const SETUP_PROMPT_SLUG = "user-profile-collection";
  const COURSE_INIT_PROMPT_SLUG = "course-session-init";
  const effectivePromptSlug = !hasProfile
    ? SETUP_PROMPT_SLUG
    : selectedPromptSlug === "default"
      ? COURSE_INIT_PROMPT_SLUG
      : selectedPromptSlug;

  // When sendMessage creates a new conversation (no initSession path — e.g. new users
  // without a profile), update the URL so the conversation is addressable and survives
  // a refresh.
  useEffect(() => {
    if (!conversationId && streamedConversationId) {
      router.replace(`/u/${userId}/chat/${streamedConversationId}`);
    }
  }, [conversationId, streamedConversationId, userId, router]);

  const isStreaming = status === "connecting" || status === "streaming";
  const isEnded = Boolean(data?.ended_at);
  const isActive = Boolean(activeConversationId) && !isEnded;

  // When inside an active conversation the prompt is locked — the course was chosen
  // at creation and cannot change mid-session. Show it as a static label.
  const lockedPromptSlug = isActive ? (data?.prompt_slug ?? null) : null;

  // True when the active conversation is the setup flow (profile + goal collection).
  // The conversation's prompt_slug is the authoritative signal — set at creation,
  // never changes mid-session.
  const isSetupConversation = isActive && data?.prompt_slug === SETUP_PROMPT_SLUG;

  // Auto-open the AI's first message on a fresh chat — per the design principle
  // "AI always opens, no blank input ever". Covers both audiences:
  //   - new users  → the setup flow (effectivePromptSlug = SETUP_PROMPT_SLUG)
  //   - profiled users → their selected course (effectivePromptSlug = selectedPromptSlug)
  // Only fires when:
  //   - userStatus has resolved (so effectivePromptSlug points at the right prompt)
  //   - there's no URL conversationId (not resuming an existing conversation)
  //   - the streaming hook is idle (no in-flight request)
  // The ref prevents re-fire if the effect re-runs while the request is in flight.
  const autoFiredRef = useRef(false);
  useEffect(() => {
    if (!conversationId && !autoFiredRef.current && status === "idle" && userStatus !== undefined) {
      autoFiredRef.current = true;
      initSession(effectivePromptSlug, selectedModelSlug, (activeId) => {
        router.push(`/u/${userId}/chat/${activeId}`);
      });
    }
  }, [conversationId, status, userStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  const { data: sessionSummary } = useSessionSummary(userId, activeConversationId, isEnded);
  const [summaryVisible, setSummaryVisible] = useState(true);

  const [endSessionError, setEndSessionError] = useState<string | null>(null);
  const [completeSetupError, setCompleteSetupError] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const { mutate: endSessionMutate, isPending: isEndingSession } = useMutation({
    mutationFn: () => endSession(userId, activeConversationId!),
    onMutate: () => setEndSessionError(null),
    onSuccess: () => {
      setSummaryVisible(true);
      queryClient.invalidateQueries({ queryKey: ["session-summary", userId, activeConversationId] });
      queryClient.invalidateQueries({ queryKey: ["messages", userId, activeConversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations", userId] });
    },
    onError: (err: Error) => {
      setEndSessionError(err.message ?? "Failed to end session. Please try again.");
    },
  });

  const { mutate: completeSetupMutate, isPending: isCompletingSetup } = useMutation({
    mutationFn: () => completeSetup(userId, activeConversationId!),
    onMutate: () => setCompleteSetupError(null),
    onSuccess: () => {
      // The backend has written sections/user and sections/course. Update the
      // cached status immediately so setup auto-start cannot race and reopen.
      queryClient.setQueryData(["user-status", userId], { has_profile: true });
      queryClient.invalidateQueries({ queryKey: ["user-status", userId] });
      queryClient.invalidateQueries({ queryKey: ["messages", userId, activeConversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations", userId] });
      reset();
      setLocalMessages([]);
      setSummaryVisible(true);
      initSession(COURSE_INIT_PROMPT_SLUG, selectedModelSlug, (activeId) => {
        router.push(`/u/${userId}/chat/${activeId}`);
      });
    },
    onError: (err: Error) => {
      setCompleteSetupError(err.message ?? "Failed to complete setup. Please try again.");
    },
  });

  const handleNewConversation = () => {
    reset();
    setLocalMessages([]);
    setSummaryVisible(true);
    // If the user has a profile, fire the AI-initiated opening message immediately.
    // The course/prompt is whichever is currently selected in the selector — locked in
    // for the life of this conversation.
    if (hasProfile) {
      initSession(effectivePromptSlug, selectedModelSlug, (activeId) => {
        router.push(`/u/${userId}/chat/${activeId}`);
      });
    } else {
      router.push(`/u/${userId}/chat`);
    }
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

    rewindAndStream(activeConversationId, messageId, newContent, effectivePromptSlug);
  };

  const handleSend = (text: string) => {
    // Don't create a conversation before we know the user's profile status —
    // see awaitingUserStatus. The input is disabled in this window; this is a guard.
    if (awaitingUserStatus) return;

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
      { messages: [{ role: "user", content: text }], prompt_slug: effectivePromptSlug, model_slug: selectedModelSlug },
      activeConversationId
    );
  };

  // Download the full conversation as a single human- and machine-readable
  // Markdown file. Includes the session summary when the session has been wrapped.
  const handleDownload = () => {
    if (!activeConversationId || localMessages.length === 0) return;
    const promptSlug = data?.prompt_slug ?? lockedPromptSlug;
    const markdown = conversationToMarkdown({
      conversationId: activeConversationId,
      name: promptSlug,
      promptSlug,
      createdAt: localMessages[0]?.created_at ?? null,
      endedAt: data?.ended_at ?? null,
      messages: localMessages,
      summary: isEnded ? sessionSummary ?? null : null,
    });
    downloadTextFile(
      conversationFilename({ conversationId: activeConversationId, name: promptSlug }),
      markdown,
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
          <Button
            variant="ghost"
            size="icon"
            title={isActive ? "End the current session before starting a new one" : "New conversation"}
            onClick={handleNewConversation}
            disabled={isActive}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <Separator />
        <div className="flex-1 overflow-y-auto">
          <ConversationList userId={userId} activeConversationId={conversationId} />
        </div>
      </aside>

      {/* Main chat area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center gap-2 border-b px-4 py-2">
          <Button variant="ghost" size="icon" onClick={toggleSidebar} title="Toggle sidebar">
            <PanelLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleNewConversation}
            title={isActive ? "End the current session before starting a new one" : "New conversation"}
            disabled={isActive}
          >
            <SquarePen className="h-4 w-4" />
          </Button>
          <PromptSelector lockedSlug={lockedPromptSlug} />
          <ModelSelector />
          <div className="ml-auto flex items-center gap-2">
            {activeConversationId && !isStreaming && !isEnded && isSetupConversation && (
              <Button
                variant="default"
                size="sm"
                onClick={() => completeSetupMutate()}
                disabled={isCompletingSetup}
                className="gap-1.5 text-xs"
                title="Confirm your course and start learning"
              >
                {isCompletingSetup ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Sparkles className="h-3.5 w-3.5" />
                )}
                {isCompletingSetup ? "Setting up…" : "Let's start"}
              </Button>
            )}
            {activeConversationId && !isStreaming && !isEnded && !isSetupConversation && (
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
            {activeConversationId && localMessages.length > 0 && !isStreaming && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDownload}
                title="Download this conversation as Markdown"
                className="gap-1.5 text-xs text-muted-foreground"
              >
                <Download className="h-3.5 w-3.5" />
                Download
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
        {completeSetupError && (
          <div className="mx-4 mb-2 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            Setup completion failed: {completeSetupError}
          </div>
        )}

        {/* Input */}
        <div className={cn("border-t p-4", isEnded && summaryVisible && "overflow-y-auto max-h-[60vh]")}>
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
            <ChatInput onSend={handleSend} disabled={awaitingUserStatus} enterToSend={enterToSend} />
          )}
        </div>
      </div>
    </div>
  );
}
