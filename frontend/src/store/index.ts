import { create } from 'zustand'
import { Message, Conversation, Fact, Task, CalendarEvent, PersonalityState, Activity, View } from '../types'

interface AppState {
  // Navigation
  activeView: View
  setView: (v: View) => void

  // Chat
  conversations: Conversation[]
  activeConversationId: number | null
  messages: Message[]
  isStreaming: boolean
  streamingContent: string
  setConversations: (c: Conversation[]) => void
  setActiveConversation: (id: number | null) => void
  addMessage: (m: Message) => void
  setMessages: (m: Message[]) => void
  setStreaming: (s: boolean) => void
  appendStreamToken: (t: string) => void
  clearStreamBuffer: () => void

  // Memory
  facts: Fact[]
  personality: PersonalityState | null
  activities: Activity[]
  setFacts: (f: Fact[]) => void
  setPersonality: (p: PersonalityState) => void
  setActivities: (a: Activity[]) => void

  // Calendar
  tasks: Task[]
  events: CalendarEvent[]
  setTasks: (t: Task[]) => void
  setEvents: (e: CalendarEvent[]) => void

  // View mode
  viewMode: 'dev' | 'user' | 'luna'
  _priorViewMode: 'dev' | 'user'
  toggleViewMode: () => void
  enterLunaDashboard: () => void
  exitLunaDashboard: () => void

  // Status
  ollamaOnline: boolean
  setOllamaOnline: (v: boolean) => void

  // Map overlay
  mapOverlayOpen: boolean
  openMapOverlay: () => void
  closeMapOverlay: () => void
  mapPendingSearch: string | null
  mapPendingRoute: string | null
  setMapPendingSearch: (q: string | null) => void
  setMapPendingRoute: (q: string | null) => void

  // Away mode
  awayMode: boolean
  enterAwayMode: () => void
  exitAwayMode: () => void

  // Dynamic explanation widget
  dynamicWidget: { kind: string; title: string; body: string } | null
  openDynamicWidget: (w: { kind: string; title: string; body: string }) => void
  closeDynamicWidget: () => void

  // Proactive messages
  proactiveMessages: string[]
  addProactiveMessage: (m: string) => void
  clearProactive: () => void

  // Confirmation UX (#10)
  pendingConfirmation: { confirm_id: string; message: string; tool: string; args: Record<string, unknown> } | null
  setPendingConfirmation: (c: AppState['pendingConfirmation']) => void
  clearPendingConfirmation: () => void

  // Plan mode (#8)
  activePlan: { steps: string[]; current: number; total: number } | null
  setActivePlan: (p: AppState['activePlan']) => void
  clearActivePlan: () => void
}

export const useStore = create<AppState>((set) => ({
  activeView: 'chat',
  setView: (v) => set({ activeView: v }),

  conversations: [],
  activeConversationId: null,
  messages: [],
  isStreaming: false,
  streamingContent: '',
  setConversations: (conversations) => set({ conversations }),
  setActiveConversation: (id) => set({ activeConversationId: id }),
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  setMessages: (messages) => set({ messages }),
  setStreaming: (isStreaming) => set({ isStreaming }),
  appendStreamToken: (t) => set((s) => ({ streamingContent: s.streamingContent + t })),
  clearStreamBuffer: () => set({ streamingContent: '' }),

  facts: [],
  personality: null,
  activities: [],
  setFacts: (facts) => set({ facts }),
  setPersonality: (personality) => set({ personality }),
  setActivities: (activities) => set({ activities }),

  tasks: [],
  events: [],
  setTasks: (tasks) => set({ tasks }),
  setEvents: (events) => set({ events }),

  viewMode: 'user',
  _priorViewMode: 'user',
  toggleViewMode: () => set((s) => {
    if (s.viewMode === 'luna') return {}
    return { viewMode: s.viewMode === 'dev' ? 'user' : 'dev' }
  }),
  enterLunaDashboard: () => set((s) => ({
    _priorViewMode: (s.viewMode !== 'luna' ? s.viewMode : s._priorViewMode) as 'dev' | 'user',
    viewMode: 'luna',
  })),
  exitLunaDashboard: () => set((s) => ({ viewMode: s._priorViewMode })),

  ollamaOnline: false,
  setOllamaOnline: (ollamaOnline) => set({ ollamaOnline }),

  mapOverlayOpen: false,
  openMapOverlay: () => set({ mapOverlayOpen: true }),
  closeMapOverlay: () => set({ mapOverlayOpen: false }),
  mapPendingSearch: null,
  mapPendingRoute: null,
  setMapPendingSearch: (q) => set({ mapPendingSearch: q }),
  setMapPendingRoute: (q) => set({ mapPendingRoute: q }),

  awayMode: false,
  enterAwayMode: () => set({ awayMode: true }),
  exitAwayMode: () => set({ awayMode: false }),

  dynamicWidget: null,
  openDynamicWidget: (dynamicWidget) => set({ dynamicWidget }),
  closeDynamicWidget: () => set({ dynamicWidget: null }),

  proactiveMessages: [],
  addProactiveMessage: (m) => set((s) => ({ proactiveMessages: [...s.proactiveMessages, m] })),
  clearProactive: () => set({ proactiveMessages: [] }),

  pendingConfirmation: null,
  setPendingConfirmation: (c) => set({ pendingConfirmation: c }),
  clearPendingConfirmation: () => set({ pendingConfirmation: null }),

  activePlan: null,
  setActivePlan: (p) => set({ activePlan: p }),
  clearActivePlan: () => set({ activePlan: null }),
}))
