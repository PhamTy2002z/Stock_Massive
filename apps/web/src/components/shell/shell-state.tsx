"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
} from "react"

import { readPreferences, writePreferences } from "@/lib/alpha-desk/preferences"

export type ShellView = "chat"
export type InspectorTab = "sources"
export type Overlay =
  | "account"
  | "attach"
  | "thread"
  | "share"
  | "palette"
  | "settings"
  | "capture"

export interface SelectedSymbol {
  symbol: string
  name: string
  exchange: string
}

interface ShellState {
  view: ShellView
  sidebarOpen: boolean
  inspector: InspectorTab | null
  chatWidth: number | null
  dragging: boolean
  sourcesMessageId: number | null
  attachRequests: number
  selected: SelectedSymbol
  contextSymbol: string | null
  overlay: Overlay | null
  viewport: number
  draft: string
}

type Action =
  | { type: "view"; view: ShellView }
  | { type: "toggle-sidebar" }
  | { type: "open-inspector"; tab: InspectorTab }
  | { type: "open-sources"; messageId: number }
  | { type: "close-inspector" }
  | { type: "resize-chat"; width: number }
  | { type: "dragging"; dragging: boolean }
  | { type: "restore-layout"; sidebarOpen: boolean | null; chatWidth: number | null }
  | { type: "thread"; opened: boolean }
  | { type: "select-symbol"; selected: SelectedSymbol; open?: boolean }
  | { type: "context-symbol"; symbol: string | null }
  | { type: "overlay"; overlay: Overlay | null }
  | { type: "viewport"; width: number }
  | { type: "draft"; text: string }
  | { type: "ask"; text: string }
  | { type: "pick-attachment" }

export const SIDEBAR_WIDTH = 274
const SOURCE_DRAWER_WIDTH = 408
const CHAT_MIN = 380
const COMPACT_VIEWPORT = 768

export function isCompact(viewport: number): boolean {
  return viewport > 0 && viewport < COMPACT_VIEWPORT
}

export function sidebarWouldFloat(state: ShellState): boolean {
  if (isCompact(state.viewport)) return true
  if (state.inspector !== null) {
    return (state.viewport || 1440) < SIDEBAR_WIDTH + CHAT_MIN + SOURCE_DRAWER_WIDTH
  }
  return false
}

export function sidebarFloats(state: ShellState): boolean {
  return state.sidebarOpen && sidebarWouldFloat(state)
}

export function inspectorWidth(state: ShellState): number {
  if (state.inspector === null || isCompact(state.viewport)) return 0
  return Math.min(SOURCE_DRAWER_WIDTH, Math.max(0, (state.viewport || 1440) - CHAT_MIN))
}

export function chatColumnWidth(state: ShellState): number {
  return Math.max(CHAT_MIN, state.chatWidth ?? 720)
}

export function maxChatWidth(state: ShellState): number {
  return Math.max(CHAT_MIN, (state.viewport || 1440) - SOURCE_DRAWER_WIDTH)
}

export { CHAT_MIN as MIN_CHAT_WIDTH }

const INITIAL: ShellState = {
  view: "chat",
  sidebarOpen: true,
  inspector: null,
  chatWidth: null,
  dragging: false,
  sourcesMessageId: null,
  attachRequests: 0,
  selected: { symbol: "VNINDEX", name: "VN-Index", exchange: "HOSE" },
  contextSymbol: null,
  overlay: null,
  viewport: 0,
  draft: "",
}

function reduce(state: ShellState, action: Action): ShellState {
  switch (action.type) {
    case "view":
      return { ...state, view: action.view }
    case "toggle-sidebar":
      return { ...state, sidebarOpen: !state.sidebarOpen, overlay: null }
    case "open-inspector":
      return { ...state, inspector: action.tab, overlay: null }
    case "open-sources":
      return {
        ...state,
        inspector: "sources",
        sourcesMessageId: action.messageId,
        overlay: null,
      }
    case "close-inspector":
      return { ...state, inspector: null, sourcesMessageId: null }
    case "resize-chat":
      return { ...state, chatWidth: action.width }
    case "dragging":
      return { ...state, dragging: action.dragging }
    case "restore-layout":
      return {
        ...state,
        sidebarOpen: action.sidebarOpen ?? state.sidebarOpen,
        chatWidth: action.chatWidth,
      }
    case "thread":
      return {
        ...state,
        inspector: null,
        sourcesMessageId: null,
        overlay: null,
        draft: action.opened ? "" : state.draft,
      }
    case "select-symbol":
      return { ...state, selected: action.selected }
    case "context-symbol":
      return { ...state, contextSymbol: action.symbol }
    case "overlay":
      return { ...state, overlay: action.overlay }
    case "viewport":
      return {
        ...state,
        viewport: action.width,
        sidebarOpen: action.width < COMPACT_VIEWPORT ? false : state.sidebarOpen,
      }
    case "draft":
      return { ...state, draft: action.text }
    case "ask":
      return { ...state, draft: action.text, view: "chat", overlay: null }
    case "pick-attachment":
      return { ...state, attachRequests: state.attachRequests + 1, overlay: null }
  }
}

interface ShellApi {
  state: ShellState
  dispatch: (action: Action) => void
  panelWidth: number
}

const ShellContext = createContext<ShellApi | null>(null)

export function ShellProvider({ children }: { children: ReactNode }) {
  const [state, rawDispatch] = useReducer(reduce, INITIAL)
  const latest = useRef(state)
  latest.current = state

  const dispatch = useCallback((action: Action) => {
    if (action.type === "toggle-sidebar" && !sidebarWouldFloat(latest.current)) {
      writePreferences({ sidebarOpen: !latest.current.sidebarOpen })
    }
    rawDispatch(action)
  }, [])

  useEffect(() => {
    const saved = readPreferences()
    rawDispatch({
      type: "restore-layout",
      sidebarOpen: saved.sidebarOpen,
      chatWidth: saved.chatWidth,
    })
  }, [])

  useEffect(() => {
    const measure = () => rawDispatch({ type: "viewport", width: window.innerWidth })
    measure()
    window.addEventListener("resize", measure)
    return () => window.removeEventListener("resize", measure)
  }, [])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        if (state.overlay !== null) dispatch({ type: "overlay", overlay: null })
        else if (state.inspector !== null) dispatch({ type: "close-inspector" })
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        dispatch({ type: "overlay", overlay: "palette" })
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "u") {
        event.preventDefault()
        dispatch({ type: "pick-attachment" })
      }
      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.code === "Comma") {
        event.preventDefault()
        dispatch({ type: "overlay", overlay: "settings" })
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [dispatch, state.inspector, state.overlay])

  const value = useMemo(
    () => ({ state, dispatch, panelWidth: inspectorWidth(state) }),
    [dispatch, state],
  )
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>
}

export function ShellSnapshot({
  value,
  children,
}: {
  value: ShellApi
  children: ReactNode
}) {
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>
}

export type { ShellApi }

export function useShell(): ShellApi {
  const value = useContext(ShellContext)
  if (value === null) throw new Error("useShell must be used inside <ShellProvider>")
  return value
}

export function useChatColumnDrag() {
  const { state, dispatch } = useShell()
  const startWidth = chatColumnWidth(state)
  return useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      const startX = event.clientX
      dispatch({ type: "dragging", dragging: true })
      const move = (moved: PointerEvent) =>
        dispatch({ type: "resize-chat", width: startWidth + moved.clientX - startX })
      const up = () => {
        dispatch({ type: "dragging", dragging: false })
        window.removeEventListener("pointermove", move)
        window.removeEventListener("pointerup", up)
      }
      window.addEventListener("pointermove", move)
      window.addEventListener("pointerup", up)
    },
    [dispatch, startWidth],
  )
}

export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  return mounted
}
