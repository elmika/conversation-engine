import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ChatStore {
  activeConversationId: string | null;
  selectedPromptSlug: string;
  selectedModelSlug: string | null;
  isSidebarOpen: boolean;
  enterToSend: boolean;
  setActiveConversationId: (id: string | null) => void;
  setSelectedPromptSlug: (slug: string) => void;
  setSelectedModelSlug: (slug: string | null) => void;
  toggleSidebar: () => void;
  toggleEnterToSend: () => void;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      activeConversationId: null,
      selectedPromptSlug: "default",
      selectedModelSlug: null,
      isSidebarOpen: true,
      enterToSend: true,

      setActiveConversationId: (id) => set({ activeConversationId: id }),
      setSelectedPromptSlug: (slug) => set({ selectedPromptSlug: slug }),
      setSelectedModelSlug: (slug) => set({ selectedModelSlug: slug }),
      toggleSidebar: () => set((s) => ({ isSidebarOpen: !s.isSidebarOpen })),
      toggleEnterToSend: () => set((s) => ({ enterToSend: !s.enterToSend })),
    }),
    {
      name: "chat-store",
      partialize: (s) => ({ enterToSend: s.enterToSend }),
    }
  )
);
