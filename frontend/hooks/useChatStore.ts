import { create } from "zustand";

interface ChatStore {
  activeConversationId: string | null;
  selectedPromptSlug: string;
  isSidebarOpen: boolean;
  setActiveConversationId: (id: string | null) => void;
  setSelectedPromptSlug: (slug: string) => void;
  toggleSidebar: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  activeConversationId: null,
  selectedPromptSlug: "default",
  isSidebarOpen: true,

  setActiveConversationId: (id) => set({ activeConversationId: id }),
  setSelectedPromptSlug: (slug) => set({ selectedPromptSlug: slug }),
  toggleSidebar: () => set((s) => ({ isSidebarOpen: !s.isSidebarOpen })),
}));
