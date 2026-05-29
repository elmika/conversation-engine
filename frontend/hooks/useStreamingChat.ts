"use client";

import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  createConversationStream,
  appendConversationTurnStream,
  rewindConversationStream,
  initSessionStream,
  ApiError,
} from "@/lib/api-client";
import { parseSSEStream } from "@/lib/stream-parser";
import type { ConversationRequest, Timings } from "@/lib/types";

// ---------------------------------------------------------------------------
// State machine types
// ---------------------------------------------------------------------------

export type StreamStatus = "idle" | "connecting" | "streaming" | "done" | "error";

export interface StreamingChatState {
  status: StreamStatus;
  /** Accumulated text during streaming; the final message on done. */
  partialText: string;
  /** Set when status === "done" (success path). */
  conversationId: string | null;
  timings: Timings | null;
  /** Model used for this response, captured from the SSE meta event. */
  model: string | null;
  /** Set when status === "error". */
  errorMessage: string | null;
}

const INITIAL_STATE: StreamingChatState = {
  status: "idle",
  partialText: "",
  conversationId: null,
  timings: null,
  model: null,
  errorMessage: null,
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useStreamingChat(userId: string) {
  const queryClient = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);
  const [state, setState] = useState<StreamingChatState>(INITIAL_STATE);

  const sendMessage = useCallback(
    async (body: ConversationRequest, existingConversationId?: string) => {
      // Cancel any in-progress request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState({
        status: "connecting",
        partialText: "",
        conversationId: existingConversationId ?? null,
        timings: null,
        model: null,
        errorMessage: null,
      });

      try {
        const stream = existingConversationId
          ? await appendConversationTurnStream(
              userId,
              existingConversationId,
              body,
              controller.signal
            )
          : await createConversationStream(userId, body, controller.signal);

        setState((s) => ({ ...s, status: "streaming" }));

        let finalConversationId = existingConversationId ?? null;
        let finalTimings: Timings | null = null;
        let finalModel: string | null = null;
        let accText = "";

        for await (const event of parseSSEStream(stream)) {
          if (controller.signal.aborted) break;

          if (event.event === "meta") {
            finalConversationId = event.data.conversation_id;
            finalModel = event.data.model;
          } else if (event.event === "chunk") {
            accText += event.data.delta;
            setState((s) => ({ ...s, partialText: accText }));
          } else if (event.event === "done") {
            if (event.data.error) {
              setState({
                status: "error",
                partialText: accText,
                conversationId: finalConversationId,
                timings: null,
                model: finalModel,
                errorMessage: String(event.data.error.message ?? "Stream error"),
              });
              return;
            }
            finalTimings = event.data.timings ?? null;
          }
        }

        if (controller.signal.aborted) {
          setState((s) => ({ ...s, status: "idle" }));
          return;
        }

        setState({
          status: "done",
          partialText: accText,
          conversationId: finalConversationId,
          timings: finalTimings,
          model: finalModel,
          errorMessage: null,
        });

        // Invalidate so history sidebar + message list reflect the new turn
        if (finalConversationId) {
          queryClient.invalidateQueries({
            queryKey: ["messages", userId, finalConversationId],
          });
        }
        if (!existingConversationId) {
          // New conversation created — refresh the list
          queryClient.invalidateQueries({ queryKey: ["conversations", userId] });
        }
      } catch (err) {
        if (controller.signal.aborted) {
          setState((s) => ({ ...s, status: "idle" }));
          return;
        }
        const message =
          err instanceof Error ? err.message : "An unexpected error occurred.";
        setState((s) => ({ ...s, status: "error", errorMessage: message }));
      }
    },
    [queryClient, userId]
  );

  const rewindAndStream = useCallback(
    async (
      conversationId: string,
      messageId: number,
      newContent: string,
      promptSlug?: string | null
    ) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState({
        status: "connecting",
        partialText: "",
        conversationId,
        timings: null,
        model: null,
        errorMessage: null,
      });

      try {
        const stream = await rewindConversationStream(
          userId,
          conversationId,
          messageId,
          newContent,
          promptSlug,
          controller.signal
        );

        setState((s) => ({ ...s, status: "streaming" }));

        let finalTimings: Timings | null = null;
        let finalModel: string | null = null;
        let accText = "";

        for await (const event of parseSSEStream(stream)) {
          if (controller.signal.aborted) break;

          if (event.event === "meta") {
            finalModel = event.data.model;
          } else if (event.event === "chunk") {
            accText += event.data.delta;
            setState((s) => ({ ...s, partialText: accText }));
          } else if (event.event === "done") {
            if (event.data.error) {
              setState({
                status: "error",
                partialText: accText,
                conversationId,
                timings: null,
                model: finalModel,
                errorMessage: String(event.data.error.message ?? "Stream error"),
              });
              return;
            }
            finalTimings = event.data.timings ?? null;
          }
        }

        if (controller.signal.aborted) {
          setState((s) => ({ ...s, status: "idle" }));
          return;
        }

        setState({
          status: "done",
          partialText: accText,
          conversationId,
          timings: finalTimings,
          model: finalModel,
          errorMessage: null,
        });

        queryClient.invalidateQueries({ queryKey: ["messages", userId, conversationId] });
      } catch (err) {
        if (controller.signal.aborted) {
          setState((s) => ({ ...s, status: "idle" }));
          return;
        }
        const message =
          err instanceof Error ? err.message : "An unexpected error occurred.";
        setState((s) => ({ ...s, status: "error", errorMessage: message }));
      }
    },
    [queryClient, userId]
  );

  const initSession = useCallback(
    async (
      promptSlug?: string | null,
      modelSlug?: string | null,
      onActiveConversation?: (conversationId: string) => void,
    ) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState({
        status: "connecting",
        partialText: "",
        conversationId: null,
        timings: null,
        model: null,
        errorMessage: null,
      });

      try {
        const stream = await initSessionStream(
          userId,
          { prompt_slug: promptSlug, model_slug: modelSlug },
          controller.signal
        );

        setState((s) => ({ ...s, status: "streaming" }));

        let finalConversationId: string | null = null;
        let finalTimings: Timings | null = null;
        let finalModel: string | null = null;
        let accText = "";

        for await (const event of parseSSEStream(stream)) {
          if (controller.signal.aborted) break;

          if (event.event === "meta") {
            finalConversationId = event.data.conversation_id;
            finalModel = event.data.model;
          } else if (event.event === "chunk") {
            accText += event.data.delta;
            setState((s) => ({ ...s, partialText: accText }));
          } else if (event.event === "done") {
            if (event.data.error) {
              if (event.data.error.status_code === 409 && onActiveConversation) {
                const activeId = event.data.error.conversation_id;
                if (activeId) {
                  setState(INITIAL_STATE);
                  onActiveConversation(String(activeId));
                  return;
                }
              }
              setState({
                status: "error",
                partialText: accText,
                conversationId: finalConversationId,
                timings: null,
                model: finalModel,
                errorMessage: String(event.data.error.message ?? "Failed to open session"),
              });
              return;
            }
            finalTimings = event.data.timings ?? null;
          }
        }

        if (controller.signal.aborted) {
          setState((s) => ({ ...s, status: "idle" }));
          return;
        }

        setState({
          status: "done",
          partialText: accText,
          conversationId: finalConversationId,
          timings: finalTimings,
          model: finalModel,
          errorMessage: null,
        });

        if (finalConversationId) {
          queryClient.invalidateQueries({ queryKey: ["messages", userId, finalConversationId] });
          queryClient.invalidateQueries({ queryKey: ["conversations", userId] });
        }
      } catch (err) {
        if (controller.signal.aborted) {
          setState((s) => ({ ...s, status: "idle" }));
          return;
        }
        // 409: an active session already exists — navigate to it instead of showing an error
        if (err instanceof ApiError && err.status === 409 && onActiveConversation) {
          const activeId = (err.detail as { conversation_id?: string } | null)?.conversation_id;
          if (activeId) {
            setState(INITIAL_STATE);
            onActiveConversation(activeId);
            return;
          }
        }
        const message = err instanceof Error ? err.message : "An unexpected error occurred.";
        setState((s) => ({ ...s, status: "error", errorMessage: message }));
      }
    },
    [queryClient, userId]
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState(INITIAL_STATE);
  }, []);

  return { ...state, sendMessage, initSession, rewindAndStream, cancel, reset };
}
