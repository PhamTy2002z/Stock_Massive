"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useState,
  type ReactNode,
} from "react"

/**
 * Every piece of chrome state the shell owns, in one reducer.
 *
 * The reference is a single-surface app: the sidebar, the three main views, the
 * inspector and four overlays are not routes, they are one screen's worth of
 * state that moves together. Splitting them across `useState` calls in the
 * layout would mean the rules that couple them — an inspector that squeezes the
 * sidebar shut, an overlay that closes every other overlay — living in effects
 * that fire in whatever order React scheduled them.
 *
 * So the coupling is written once, here, as transitions.
 */

/** What fills the main column. Client state, deliberately: the reference switches
 *  these without a navigation, and the composer must survive the switch. */
export type ShellView = "chat" | "board" | "new" | "news"

/** Which tab the right-hand inspector shows, or `null` when it is closed. */
export type InspectorTab = "market" | "symbol" | "news"

/** The four things that float above the surface. One at a time, always. */
export type Overlay = "account" | "attach" | "thread" | "share" | "palette"

export interface SelectedSymbol {
  symbol: string
  name: string
  exchange: string
}

interface ShellState {
  view: ShellView
  sidebarOpen: boolean
  inspector: InspectorTab | null
  /** Explicit width in px once the user has dragged the handle; null until then. */
  inspectorWidth: number | null
  inspectorWide: boolean
  /** True while the handle is held: transitions are suppressed so the drag tracks. */
  dragging: boolean
  selected: SelectedSymbol
  /** The symbol the composer sends as the Turn's analysis context. */
  contextSymbol: string | null
  overlay: Overlay | null
  noticeDismissed: boolean
  /** Viewport width, measured after mount. 0 until then — see `useViewport`. */
  viewport: number
  /**
   * What is in the composer, held here rather than in the composer.
   *
   * Two surfaces mount a composer — the opening screen and the docked one — and
   * switching between them must not lose a half-typed question. It is also what
   * lets another panel *offer* a question: the board's "Hỏi VisgniteAI" fills
   * the field and leaves the user to press send, rather than sending on their
   * behalf.
   */
  draft: string
  /**
   * Which article the news view has open, as `"SYMBOL:id"`, or `null` for the feed.
   *
   * Here rather than in the news view for the same reason as `draft`: reading an
   * article is not a navigation, so glancing at the board and coming back must
   * return to the paragraph the reader was on rather than to the top of the
   * feed. It is also what lets the inspector's source tab exist at all — that
   * panel is a second surface describing the same open article.
   */
  newsArticle: string | null
}

type Action =
  | { type: "view"; view: ShellView }
  | { type: "toggle-sidebar" }
  | { type: "open-inspector"; tab: InspectorTab }
  | { type: "close-inspector" }
  | { type: "toggle-inspector-wide" }
  | { type: "resize-inspector"; width: number }
  | { type: "reset-inspector-width" }
  | { type: "dragging"; dragging: boolean }
  | { type: "select-symbol"; selected: SelectedSymbol; open?: boolean }
  | { type: "context-symbol"; symbol: string | null }
  | { type: "overlay"; overlay: Overlay | null }
  | { type: "dismiss-notice" }
  | { type: "viewport"; width: number }
  | { type: "draft"; text: string }
  /** Open one article in the news view, or `null` to go back to the feed. */
  | { type: "news-article"; article: string | null }
  /** Fill the composer and put the user in front of it, without sending. */
  | { type: "ask"; text: string }

/** The reference's own numbers. */
export const SIDEBAR_WIDTH = 274
const INSPECTOR_DEFAULT = 408
const INSPECTOR_MIN = 320
/** Below this the conversation stops being a conversation and becomes a gutter. */
const CONVERSATION_MIN = 520

/** What the inspector is currently worth in pixels, closed included. */
export function inspectorWidth(state: ShellState): number {
  if (state.inspector === null) return 0
  if (state.inspectorWidth !== null) return state.inspectorWidth
  if (state.inspectorWide) {
    return Math.min(760, Math.round((state.viewport || 1440) * 0.52))
  }
  return INSPECTOR_DEFAULT
}

/** The widest the handle may drag to, leaving the conversation something to be. */
export function maxInspectorWidth(viewport: number): number {
  return Math.min(1000, Math.max(360, (viewport || 1440) - 420))
}

const INITIAL: ShellState = {
  view: "chat",
  sidebarOpen: true,
  inspector: null,
  inspectorWidth: null,
  inspectorWide: false,
  dragging: false,
  selected: { symbol: "VCB", name: "Ngân hàng TMCP Ngoại thương Việt Nam", exchange: "HOSE" },
  contextSymbol: null,
  overlay: null,
  noticeDismissed: false,
  viewport: 0,
  draft: "",
  newsArticle: null,
}

/**
 * Opening the inspector on a viewport that cannot hold all three columns folds
 * the sidebar rather than crushing the conversation.
 *
 * Applied on the transition rather than in an effect watching the result: an
 * effect would fire after the frame that already drew the squeezed layout, and
 * the user would see the conversation snap thin and then recover.
 */
function foldSidebarIfCramped(state: ShellState): ShellState {
  if (!state.sidebarOpen || state.inspector === null) return state
  const room = state.viewport - inspectorWidth(state) - SIDEBAR_WIDTH
  // Before the first measurement there is nothing to decide against, and
  // guessing would fold the sidebar on every server render.
  if (state.viewport === 0 || room >= CONVERSATION_MIN) return state
  return { ...state, sidebarOpen: false }
}

function reduce(state: ShellState, action: Action): ShellState {
  switch (action.type) {
    case "view":
      // Switching views closes whatever was floating: every overlay belongs to
      // the view that opened it.
      return { ...state, view: action.view, overlay: null }

    case "toggle-sidebar":
      return { ...state, sidebarOpen: !state.sidebarOpen }

    case "open-inspector":
      return foldSidebarIfCramped({ ...state, inspector: action.tab, overlay: null })

    case "close-inspector":
      // The width goes back to the default with it. A panel reopened at
      // yesterday's drag width would be a setting nobody asked to keep.
      return { ...state, inspector: null, inspectorWide: false, inspectorWidth: null }

    case "toggle-inspector-wide":
      return foldSidebarIfCramped({
        ...state,
        inspectorWide: !state.inspectorWide,
        inspectorWidth: null,
      })

    case "resize-inspector":
      return foldSidebarIfCramped({
        ...state,
        inspectorWidth: Math.max(
          INSPECTOR_MIN,
          Math.min(maxInspectorWidth(state.viewport), action.width),
        ),
      })

    case "reset-inspector-width":
      return { ...state, inspectorWidth: null, inspectorWide: false }

    case "dragging":
      return { ...state, dragging: action.dragging }

    case "select-symbol": {
      const next: ShellState = { ...state, selected: action.selected }
      if (!action.open) return next
      return foldSidebarIfCramped({ ...next, inspector: "symbol", overlay: null })
    }

    case "context-symbol":
      return { ...state, contextSymbol: action.symbol }

    case "overlay":
      return { ...state, overlay: action.overlay }

    case "dismiss-notice":
      return { ...state, noticeDismissed: true }

    case "viewport":
      return foldSidebarIfCramped({ ...state, viewport: action.width })

    case "draft":
      return { ...state, draft: action.text }

    case "news-article":
      // An article opening is a change of what the main column reads, so
      // whatever was floating over it belongs to the screen being left.
      return { ...state, newsArticle: action.article, overlay: null }

    case "ask":
      // The question is offered, not asked. Landing in the conversation with
      // the sentence already in the field is what makes it the user's.
      return { ...state, draft: action.text, view: "chat", overlay: null }
  }
}

interface ShellApi {
  state: ShellState
  dispatch: (action: Action) => void
  /** Derived, because three components need it and none of them owns it. */
  panelWidth: number
}

const ShellContext = createContext<ShellApi | null>(null)

export function ShellProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reduce, INITIAL)

  // Measured after mount rather than read during render: `window` does not
  // exist on the server, and seeding a guess would make the first client tree
  // disagree with the HTML it is hydrating.
  useEffect(() => {
    const measure = () => dispatch({ type: "viewport", width: window.innerWidth })
    measure()
    window.addEventListener("resize", measure)
    return () => window.removeEventListener("resize", measure)
  }, [])

  // Escape closes whatever floats; ⌘K / Ctrl+K opens the palette from anywhere.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") dispatch({ type: "overlay", overlay: null })
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        dispatch({ type: "overlay", overlay: "palette" })
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  const value = useMemo<ShellApi>(
    () => ({ state, dispatch, panelWidth: inspectorWidth(state) }),
    [state],
  )

  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>
}

export function useShell(): ShellApi {
  const value = useContext(ShellContext)
  if (value === null) throw new Error("useShell must be used inside <ShellProvider>")
  return value
}

/**
 * Dragging the inspector's left edge.
 *
 * Pointer events rather than mouse events, so a trackpad, a pen and a touch
 * screen all resize the same way. Listeners go on the window because the
 * pointer leaves the 9px handle almost immediately.
 */
export function useInspectorDrag() {
  const { dispatch, panelWidth } = useShell()

  return useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      const startX = event.clientX
      const startWidth = panelWidth
      dispatch({ type: "dragging", dragging: true })

      // The panel is on the right, so it widens as the pointer travels left.
      const move = (moved: PointerEvent) =>
        dispatch({ type: "resize-inspector", width: startWidth + (startX - moved.clientX) })

      const up = () => {
        dispatch({ type: "dragging", dragging: false })
        window.removeEventListener("pointermove", move)
        window.removeEventListener("pointerup", up)
      }

      window.addEventListener("pointermove", move)
      window.addEventListener("pointerup", up)
    },
    // The clamp reads the viewport from the reducer's own state, so this does
    // not need it as a dependency — a resize mid-drag is still bounded.
    [dispatch, panelWidth],
  )
}

/**
 * True once the browser has painted, false during the server render.
 *
 * Used by the few places that must not render a browser-only value into the
 * HTML — the greeting reads the clock, and a server that says "Evening" to a
 * browser at breakfast is a hydration mismatch, not a stale string.
 */
export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  return mounted
}
