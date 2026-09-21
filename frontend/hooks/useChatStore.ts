import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ChatStore {
  activeConversationId: string | null;
  isSidebarOpen: boolean;
  enterToSend: boolean;
  setActiveConversationId: (id: string | null) => void;
  toggleSidebar: () => void;
  toggleEnterToSend: () => void;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      activeConversationId: null,
      isSidebarOpen: true,
      enterToSend: true,

      setActiveConversationId: (id) => set({ activeConversationId: id }),
      toggleSidebar: () => set((s) => ({ isSidebarOpen: !s.isSidebarOpen })),
      toggleEnterToSend: () => set((s) => ({ enterToSend: !s.enterToSend })),
    }),
    {
      name: "chat-store",
      partialize: (s) => ({ enterToSend: s.enterToSend }),
    }
  )
);
