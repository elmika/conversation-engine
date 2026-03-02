"use client";

import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  createConversationStream,
  appendConversationTurnStream,
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
  /** Set when status === "error". */
  errorMessage: string | null;
}

const INITIAL_STATE: StreamingChatState = {
  status: "idle",
  partialText: "",
  conversationId: null,
  timings: null,
  errorMessage: null,
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useStreamingChat() {
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
        errorMessage: null,
      });

      try {
        const stream = existingConversationId
          ? await appendConversationTurnStream(
              existingConversationId,
              body,
              controller.signal
            )
          : await createConversationStream(body, controller.signal);

        setState((s) => ({ ...s, status: "streaming" }));

        let finalConversationId = existingConversationId ?? null;
        let finalTimings: Timings | null = null;
        let accText = "";

        for await (const event of parseSSEStream(stream)) {
          if (controller.signal.aborted) break;

          if (event.event === "meta") {
            finalConversationId = event.data.conversation_id;
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
                errorMessage: event.data.error.message,
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
          errorMessage: null,
        });

        // Invalidate so history sidebar + message list reflect the new turn
        if (finalConversationId) {
          queryClient.invalidateQueries({
            queryKey: ["messages", finalConversationId],
          });
        }
        if (!existingConversationId) {
          // New conversation created — refresh the list
          queryClient.invalidateQueries({ queryKey: ["conversations"] });
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
    [queryClient]
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState(INITIAL_STATE);
  }, []);

  return { ...state, sendMessage, cancel, reset };
}
