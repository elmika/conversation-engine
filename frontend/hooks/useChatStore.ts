import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ChatStore {
  activeConversationId: string | null;
  selectedPromptSlug: string;
  isSidebarOpen: boolean;
  enterToSend: boolean;
  setActiveConversationId: (id: string | null) => void;
  setSelectedPromptSlug: (slug: string) => void;
  toggleSidebar: () => void;
  toggleEnterToSend: () => void;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      activeConversationId: null,
      selectedPromptSlug: "default",
      isSidebarOpen: true,
      enterToSend: true,

      setActiveConversationId: (id) => set({ activeConversationId: id }),
      setSelectedPromptSlug: (slug) => set({ selectedPromptSlug: slug }),
      toggleSidebar: () => set((s) => ({ isSidebarOpen: !s.isSidebarOpen })),
      toggleEnterToSend: () => set((s) => ({ enterToSend: !s.enterToSend })),
    }),
    {
      name: "chat-store",
      partialize: (s) => ({ enterToSend: s.enterToSend }),
    }
  )
);
