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

import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import { readPreferences, writePreferences } from "@/lib/alpha-desk/preferences"

// URL-state helpers for the market-monitor views were removed with those
// views on 2026-08-25. Only the chat view survives, so there is nothing left
// to encode in ``?view=…``; declarations live after ``ShellView`` below.

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

// See top-of-file comment: only "chat" is ever rendered now.
const writeShellViewToHistory = (_view: ShellView): void => {}
const shellViewFromSearch = (_search: string): ShellView | null => null

/** Which tab the right-hand pane shows, or `null` when it is closed. */
export type InspectorTab = "market" | "symbol" | "news" | "sources" | "deskView"

/** The things that float above the surface. One at a time, always. */
export type Overlay =
  | "account"
  | "attach"
  | "thread"
  | "share"
  | "palette"
  | "settings"
  /** The board switcher: every picture this conversation drew, searchable. */
  | "boards"
  /**
   * The screen capture, waiting to be looked at.
   *
   * An overlay rather than something inline, because this is a gate and not a
   * decoration: `getDisplayMedia` returns whatever the reader agreed to share,
   * and a capture-then-send flow sends things nobody meant to send.
   */
  | "capture"
  /** The dropdown under the header's own control: the same boards, one click away. */
  | "board-menu"

export interface SelectedSymbol {
  symbol: string
  name: string
  exchange: string
}

/**
 * One desk view the conversation has produced, as the header needs it.
 *
 * An id and a name, never the numbers: the cells are a row the pane fetches by
 * id, and a copy of them here would be a second version of one picture that
 * could disagree with the one being drawn.
 *
 * The rest is what the switcher needs to *find* it again. A working
 * conversation makes twenty boards, so the way back that scales is search —
 * which needs more than a title to search on: a reader looking for "the
 * liquidity one for STB" remembers the ticker and the recipe, not the sentence
 * the server composed out of them.
 *
 * Those four are optional because they arrive from the announcement, and an
 * announcement written by a build that predates them carries none. A board with
 * no symbol is still a board; it is only harder to type your way back to.
 */
export interface SignalDeskBoard {
  artifactId: string
  title: string
  /** The ticker the board is about, or undefined for a whole-market one. */
  symbol?: string
  /**
   * The recipe's stable name — matched against, never drawn.
   *
   * A reader who pasted a slug out of an exported file should find their board;
   * a reader who did not should never learn the slug exists.
   */
  studyName?: string
  /** The recipe's Vietnamese name. The only recipe name a person may see. */
  studyDisplayName?: string
  /** Which round of the tool loop produced it. How "Tất cả" groups. */
  round?: number
}

interface ShellState {
  view: ShellView
  sidebarOpen: boolean
  inspector: InspectorTab | null
  /**
   * Explicit width in px for the **chat column** once the user has dragged the
   * handle; null until then.
   *
   * The Signal Desk inverts which column is the fixed one. The pane is the work
   * surface and takes whatever is left, so what a drag actually sets is how much
   * of the viewport the conversation keeps — see `chatColumnWidth`.
   */
  chatWidth: number | null
  /** True while the handle is held: transitions are suppressed so the drag tracks. */
  dragging: boolean
  /**
   * Which answer the sources tab is showing, or null.
   *
   * A message id rather than the sources themselves: the transcript already
   * owns them, and a copy here would be a second version of one answer's
   * sources that could disagree with the one on screen. Null closes the tab's
   * subject — the tab has nothing to show without an answer to show it for.
   */
  sourcesMessageId: number | null
  /**
   * How many times ⌘U has asked for the file picker.
   *
   * A counter and not a boolean, because opening a picker is an event and not a
   * state: the composer owns the hidden `<input>` and watches this number, and
   * a flag would have to be set and then unset by whoever consumed it. Two
   * presses in a row have to open it twice, which a flag cannot express.
   */
  attachRequests: number
  /**
   * Every board this conversation has produced, in the order it announced them.
   *
   * The record, and the only list of boards the chrome draws from: the header's
   * dropdown and the switcher both show the lot, so nothing a Turn drew is ever
   * out of reach while the Thread is on screen.
   */
  deskBoards: SignalDeskBoard[]
  /**
   * The boards the reader keeps at the top of the list, in the order they were
   * pinned.
   *
   * Ids rather than boards, because a pin outlives the board's arrival: it is
   * restored from this browser before the Thread's messages have been read, so
   * for a moment it names boards this state has not met yet.
   */
  deskPinned: string[]
  /**
   * The same boards as ids, newest first.
   *
   * What "the newest picture" means after a restore, where the boards arrive as
   * a batch rather than one announcement at a time: the pane lands on the head
   * of this list rather than on the desk's empty state.
   */
  deskRecent: string[]
  /**
   * Which of them the pane is showing, or null.
   *
   * An artifact id rather than the spec: the numbers are a TanStack Query
   * resource keyed by that id, and a copy here would be a second version of one
   * picture that could disagree with the one being fetched.
   */
  deskViewArtifactId: string | null
  /**
   * Whether the reader chose what they are looking at.
   *
   * Set by any tab the reader opens themselves *and by dismissing the pane*,
   * because both are a decision about what this conversation should show. A
   * deskView arriving mid-answer then appends its tab without taking the surface
   * off a reader who has gone back to Sources — or put it away.
   */
  inspectorPinned: boolean
  /**
   * Whether the Signal Desk is switched on for the conversation on screen.
   *
   * A mode the reader enters, not a panel that appears: the layout inverts the
   * moment this goes true, with or without a desk view in hand. Held per Thread —
   * `desk-state` reads the remembered value back on every Thread switch, so a
   * desk left open on one conversation never follows the reader into the next.
   */
  signalDesk: boolean
  selected: SelectedSymbol
  /** The symbol the composer sends as the Turn's analysis context. */
  contextSymbol: string | null
  overlay: Overlay | null
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
  // Opens the sources tab *and* says whose sources, which is one user action.
  | { type: "open-sources"; messageId: number }
  // The same for a desk view: which picture, opened by the reader. Everything
  // but the id is optional because the transcript's card knows only the id.
  | ({ type: "open-desk-view"; artifactId: string } & Partial<SignalDeskBoard>)
  // A desk view the Turn produced. Always filed; the pane switches to it only
  // where the desk is on and the reader has not chosen something else.
  | ({ type: "signal-desk-ready"; artifactId: string } & Partial<SignalDeskBoard>)
  | { type: "desk-views-restored"; tabs: SignalDeskBoard[] }
  // Keep one board at the top of the list, or stop keeping it there.
  | { type: "pin-desk-view"; artifactId: string; pinned: boolean }
  // What this browser remembered about *this* Thread's pins. Separate from the
  // gesture for the reason `restore-layout` is: a restore is not a choice, and
  // must not be written straight back.
  | { type: "desk-pins-restored"; artifactIds: string[] }
  // The name a fetched artifact turned out to carry, for a tab that was opened
  // out of the transcript and so had only an id to go on.
  | { type: "signal-desk-title"; artifactId: string; title: string }
  | { type: "close-inspector" }
  | { type: "signal-desk"; on: boolean }
  | { type: "resize-chat"; width: number }
  | { type: "dragging"; dragging: boolean }
  // What this browser remembered about the layout, applied once after mount.
  // Separate from the actions that *change* the layout so the restore is never
  // mistaken for a gesture and written straight back.
  | { type: "restore-layout"; sidebarOpen: boolean | null; chatWidth: number | null }
  // A different conversation is on screen. Everything below belongs to the one
  // being left, including whether its desk was open. `opened` separates a
  // reader picking a conversation from the tab restoring the one it had: only
  // the first is a gesture, and only a gesture may rearrange the columns.
  | { type: "thread"; signalDesk: boolean; opened: boolean }
  | { type: "select-symbol"; selected: SelectedSymbol; open?: boolean }
  | { type: "context-symbol"; symbol: string | null }
  | { type: "overlay"; overlay: Overlay | null }
  | { type: "viewport"; width: number }
  | { type: "draft"; text: string }
  /** Open one article in the news view, or `null` to go back to the feed. */
  | { type: "news-article"; article: string | null }
  /** Fill the composer and put the user in front of it, without sending. */
  | { type: "ask"; text: string }
  | { type: "pick-attachment" }

/** The reference's own numbers. */
export const SIDEBAR_WIDTH = 274
/**
 * The chat column once the desk is open.
 *
 * The design's 420 read too narrow beside a board: an answer with two evidence
 * blocks wrapped every line. Raised by a third so the conversation stays
 * readable while the desk still has room on a 1440 viewport.
 */
const CHAT_DEFAULT = 556
/** Below this the conversation stops being a conversation and becomes a gutter. */
const CHAT_MIN = 380
/** Below this the pane cannot hold a chart beside its own axis labels. */
const SIGNAL_DESK_MIN = 480
/** One column from here down: two of them would each be too narrow to read. */
const COMPACT_VIEWPORT = 768

/** Whether the viewport is a phone's, where the pane overlays rather than splits. */
export function isCompact(viewport: number): boolean {
  return viewport > 0 && viewport < COMPACT_VIEWPORT
}

/**
 * Whether an open list lies *over* the workspace rather than beside it.
 *
 * The rule the pane already follows, applied to the other edge: a region floats
 * when there is no room to split. The pane floats on a phone for that reason,
 * and the list floats for the same one — with the desk open, the two columns
 * are already at their minimums, so a 274px column taken out of them does not
 * shrink the workspace, it breaks it.
 *
 * That is what the reader was seeing. Pulling the list out over an open desk
 * squeezed the conversation and the chart into whatever was left, and the fix
 * is not to forbid the list but to stop it taking the room: floating, it costs
 * the layout nothing and closes again on the next click outside.
 *
 * A phone is the same case with no desk needed — 274 of 390 is not a column.
 */
export function sidebarFloats(state: ShellState): boolean {
  if (!state.sidebarOpen) return false
  return sidebarWouldFloat(state)
}

/**
 * Whether the list is an overlay rather than a column, open or shut.
 *
 * Separate from `sidebarFloats` because the two questions differ for a closed
 * sidebar: nothing is floating when nothing is shown, but whether it *would*
 * float still decides whether opening and closing it is a lasting choice or a
 * dismissal. On a phone, and beside an open inspector, the list is a surface
 * laid over the workspace — putting it away there is the same gesture as
 * closing any other overlay, and no more a preference than one.
 */
export function sidebarWouldFloat(state: ShellState): boolean {
  return state.inspector !== null || isCompact(state.viewport)
}

/** What the two columns have to share, the sidebar already taken out. */
function roomForColumns(state: ShellState): number {
  // 1440 before the first measurement: something has to be assumed for the
  // server render, and assuming a desktop keeps the first paint from folding a
  // sidebar it would immediately have to unfold.
  //
  // A floating list is subtracted from nothing: it is over the workspace, not
  // in it, so every width measured here is the width it would have had with the
  // list closed.
  const rail = state.sidebarOpen && !sidebarFloats(state) ? SIDEBAR_WIDTH : 0
  return (state.viewport || 1440) - rail
}

/**
 * What the conversation is worth in pixels while the pane is open.
 *
 * Clamped from both sides on every read rather than at the moment of the drag,
 * because the room it is measured against moves without anybody dragging
 * anything — folding the sidebar and resizing the window both change it.
 */
export function chatColumnWidth(state: ShellState): number {
  const room = roomForColumns(state)
  // The desk view keeps its minimum where there is room for both, and gives it up
  // where there is not: the conversation is what the reader is reading.
  const ceiling = Math.max(CHAT_MIN, room - SIGNAL_DESK_MIN)
  return Math.min(Math.max(state.chatWidth ?? CHAT_DEFAULT, CHAT_MIN), ceiling)
}

/** The widest the chat column may be dragged to on this viewport. */
export function maxChatWidth(state: ShellState): number {
  return Math.max(CHAT_MIN, roomForColumns(state) - SIGNAL_DESK_MIN)
}

export { CHAT_MIN as MIN_CHAT_WIDTH }

/**
 * What the pane is currently worth in pixels, closed included.
 *
 * Zero on a phone as well as when closed: there the pane is an overlay laid
 * over the conversation rather than a column beside it, so it takes no width
 * away from anything and every layout that reads this keeps what it had.
 */
export function inspectorWidth(state: ShellState): number {
  if (state.inspector === null || isCompact(state.viewport)) return 0
  return Math.max(0, roomForColumns(state) - chatColumnWidth(state))
}

const INITIAL: ShellState = {
  view: "chat",
  sidebarOpen: true,
  inspector: null,
  chatWidth: null,
  sourcesMessageId: null,
  attachRequests: 0,
  deskBoards: [],
  deskPinned: [],
  deskRecent: [],
  deskViewArtifactId: null,
  inspectorPinned: false,
  signalDesk: false,
  dragging: false,
  selected: { symbol: "VCB", name: "Ngân hàng TMCP Ngoại thương Việt Nam", exchange: "HOSE" },
  contextSymbol: null,
  overlay: null,
  viewport: 0,
  draft: "",
  newsArticle: null,
}

/**
 * Opening the pane on a viewport that cannot hold all three columns folds the
 * sidebar rather than crushing the conversation.
 *
 * Applied on the transition rather than in an effect watching the result: an
 * effect would fire after the frame that already drew the squeezed layout, and
 * the user would see the conversation snap thin and then recover.
 */
function foldSidebarIfCramped(state: ShellState): ShellState {
  if (!state.sidebarOpen || state.inspector === null) return state
  // Before the first measurement there is nothing to decide against, and
  // guessing would fold the sidebar on every server render. A phone has already
  // folded it, and the pane there is an overlay in any case.
  if (state.viewport === 0 || isCompact(state.viewport)) return state
  if (state.viewport - SIDEBAR_WIDTH >= CHAT_MIN + SIGNAL_DESK_MIN) return state
  return { ...state, sidebarOpen: false }
}

/**
 * The record with this board in it, or the record itself when nothing changed.
 *
 * Identity is the contract: `desk-views-restored` runs on every change to the
 * message list, and a fresh array each time would re-render the whole shell for
 * a list that is word for word the one already held.
 */
function withBoard(boards: SignalDeskBoard[], board: SignalDeskBoard): SignalDeskBoard[] {
  const index = boards.findIndex((existing) => existing.artifactId === board.artifactId)
  if (index === -1) return [...boards, board]
  const known = boards[index]
  if (
    known.title === board.title &&
    known.symbol === board.symbol &&
    known.studyName === board.studyName &&
    known.studyDisplayName === board.studyDisplayName &&
    known.round === board.round
  ) {
    return boards
  }
  // A republished announcement is the same run, so it replaces rather than
  // adding a second board for one picture.
  const next = [...boards]
  next[index] = board
  return next
}

/** What the caller said about a board, filled in from what is already known. */
function boardFrom(
  state: ShellState,
  action: { artifactId: string } & Partial<SignalDeskBoard>,
): SignalDeskBoard {
  const known = state.deskBoards.find((board) => board.artifactId === action.artifactId)
  const title = action.title?.trim()
  return {
    artifactId: action.artifactId,
    // A desk view with no title still gets a name a person can read.
    title: title || known?.title || SIGNAL_DESK_COPY.name,
    symbol: action.symbol ?? known?.symbol,
    studyName: action.studyName ?? known?.studyName,
    studyDisplayName: action.studyDisplayName ?? known?.studyDisplayName,
    round: action.round ?? known?.round,
  }
}

/** The recency list with a board this conversation has not seen at its head. */
function fileRecent(recent: string[], artifactId: string): string[] {
  return recent.includes(artifactId) ? recent : [artifactId, ...recent]
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
      return foldSidebarIfCramped({
        ...state,
        inspector: action.tab,
        inspectorPinned: true,
        overlay: null,
      })

    case "open-sources":
      return foldSidebarIfCramped({
        ...state,
        inspector: "sources",
        sourcesMessageId: action.messageId,
        inspectorPinned: true,
        overlay: null,
      })

    case "open-desk-view": {
      // A card in the transcript is another deliberate way into the desk, so
      // it owns the same column transition as throwing the switch: the list
      // folds even where all three columns would technically fit. Unlike the
      // switch on a phone, the card then opens the full-screen pane because the
      // reader explicitly asked to see this picture.
      const withDesk = reduce(state, { type: "signal-desk", on: true })
      return {
        ...withDesk,
        inspector: "deskView",
        deskBoards: withBoard(state.deskBoards, boardFrom(state, action)),
        // A card in the transcript can name a picture this state has not met —
        // the transcript is read before the boards are restored off it.
        deskRecent: fileRecent(state.deskRecent, action.artifactId),
        deskViewArtifactId: action.artifactId,
        inspectorPinned: true,
        overlay: null,
      }
    }

    case "signal-desk-ready": {
      // The board is filed whatever the reader is looking at: they may open it
      // a minute later, and the switcher has to know the picture exists.
      const next: ShellState = {
        ...state,
        deskBoards: withBoard(state.deskBoards, boardFrom(state, action)),
        deskRecent: fileRecent(state.deskRecent, action.artifactId),
      }
      // The desk is the trigger now. A desk view arriving while it is off leaves a
      // card in the transcript and nothing else — the reader decides when the
      // layout changes under them.
      if (!state.signalDesk) return next
      // On a phone the pane would be the whole screen, which is the answer
      // taking the conversation off the reader mid-sentence.
      if (isCompact(state.viewport)) return next
      // The reader is somewhere they chose. Appending a tab is telling them;
      // switching to it would be deciding for them.
      if (state.inspectorPinned && state.inspector !== "deskView") return next
      return foldSidebarIfCramped({
        ...next,
        inspector: "deskView",
        deskViewArtifactId: action.artifactId,
        overlay: null,
      })
    }

    case "desk-views-restored": {
      // Putting back what this conversation already made, and nothing else.
      //
      // Opening a Thread clears the boards — they belonged to the conversation
      // being left. What was missing is the other half: the Thread being
      // *entered* has its own pictures, stored on its messages, and they were
      // being thrown away on every reopen.
      //
      // Deliberately inert about layout. It does not open the inspector, does
      // not switch tab, does not pin, and does not turn the desk on: a reader
      // returning to an old conversation asked for the conversation, not for a
      // panel to take a third of it. All this does is make the pictures
      // reachable in one click instead of by scrolling for the card.
      const deskBoards = action.tabs.reduce(withBoard, state.deskBoards)
      // Identity when there is nothing new, because this runs on every change
      // to the message list and a fresh array each time would re-render the
      // whole shell for no reason.
      if (deskBoards === state.deskBoards) return state
      // The boards arrive oldest first, so unshifting each one leaves the
      // recency list newest first. Only boards this conversation had not filed
      // yet are filed, so a re-announcement of the whole list on every message
      // change leaves the order the reader already has alone.
      const known = new Set(state.deskBoards.map((board) => board.artifactId))
      const deskRecent = action.tabs
        .filter((board) => !known.has(board.artifactId))
        .reduce((recent, board) => fileRecent(recent, board.artifactId), state.deskRecent)
      return {
        ...state,
        deskBoards,
        deskRecent,
        // The newest is what the header opens onto, so that reaching for the
        // desk answers immediately rather than with its own empty state. Never
        // overrides a picture already on screen.
        deskViewArtifactId: state.deskViewArtifactId ?? deskRecent[0] ?? null,
      }
    }

    case "signal-desk-title": {
      const index = state.deskBoards.findIndex(
        (board) => board.artifactId === action.artifactId,
      )
      if (index === -1 || state.deskBoards[index].title === action.title) return state
      const deskBoards = [...state.deskBoards]
      deskBoards[index] = { ...deskBoards[index], title: action.title }
      return { ...state, deskBoards }
    }

    case "pin-desk-view": {
      const pinned = state.deskPinned.includes(action.artifactId)
      if (pinned === action.pinned) return state
      // Only the pin moves. Releasing one leaves the board where the list
      // already had it, because the list holds every board either way — a
      // release that also reordered would move a row out from under the cursor
      // that had just pressed it.
      return {
        ...state,
        deskPinned: action.pinned
          ? [...state.deskPinned, action.artifactId]
          : state.deskPinned.filter((id) => id !== action.artifactId),
      }
    }

    case "desk-pins-restored": {
      const same =
        state.deskPinned.length === action.artifactIds.length &&
        state.deskPinned.every((id, at) => action.artifactIds[at] === id)
      if (same) return state
      return { ...state, deskPinned: [...action.artifactIds] }
    }

    case "close-inspector":
      // The width goes back to the default with it: a pane reopened at
      // yesterday's drag width would be a setting nobody asked to keep. The pin
      // stays *set* — putting the workspace away is a decision about this
      // conversation, and the next deskView must not undo it. And the desk goes
      // off with it, because the pill and the pane are one state and a switch
      // reading "on" over an ordinary chat layout is a lie.
      return {
        ...state,
        inspector: null,
        chatWidth: null,
        inspectorPinned: true,
        signalDesk: false,
      }

    case "signal-desk":
      if (!action.on) {
        return {
          ...state,
          signalDesk: false,
          inspector: null,
          chatWidth: null,
          inspectorPinned: false,
        }
      }
      // A phone keeps the conversation. The desk is on — a desk view still files
      // its tab and its card — but the pane opens only on a deliberate tap.
      if (isCompact(state.viewport)) return { ...state, signalDesk: true, overlay: null }
      return {
        ...state,
        signalDesk: true,
        inspector: "deskView",
        inspectorPinned: false,
        overlay: null,
        // The desk takes the room from the list, on every viewport rather than
        // only the ones too narrow to hold three columns. A desk view is the
        // widest thing this product draws, and a reader who has switched the
        // desk on is looking at pictures, not at a list of conversations. The
        // list is one keystroke and one corner away when they want it back.
        sidebarOpen: false,
      }

    case "resize-chat":
      return foldSidebarIfCramped({
        ...state,
        chatWidth: Math.max(CHAT_MIN, Math.min(maxChatWidth(state), action.width)),
      })

    case "dragging":
      return { ...state, dragging: action.dragging }

    case "restore-layout": {
      // The width is taken raw. What a width is *allowed* to be depends on the
      // viewport, which may not be measured yet, and `chatColumnWidth` already
      // clamps on read — so clamping here as well would bound the stored value
      // against a viewport of zero.
      const next = {
        ...state,
        chatWidth: action.chatWidth ?? state.chatWidth,
      }
      if (action.sidebarOpen === null) return next
      return { ...next, sidebarOpen: action.sidebarOpen }
    }

    case "thread": {
      // Everything the pane was showing belonged to the conversation being
      // left. The desk's own switch is read back per Thread rather than carried
      // across, so opening an old conversation restores what *it* was doing.
      const cleared: ShellState = {
        ...state,
        inspector: null,
        chatWidth: null,
        inspectorPinned: false,
        sourcesMessageId: null,
        deskBoards: [],
        deskPinned: [],
        deskRecent: [],
        deskViewArtifactId: null,
        signalDesk: false,
      }
      if (!action.signalDesk) return cleared
      // Applied through the same transition the switch itself uses, so there is
      // one rule for what "on" does to the layout rather than two — the fold
      // included. Picking a conversation whose desk is on therefore folds the
      // list exactly as throwing the switch does.
      const withDesk = reduce(cleared, { type: "signal-desk", on: true })
      // Restoring what the tab already had is the one exception. Nobody asked
      // for anything, and a sidebar that slides away a frame after the page
      // paints reads as a fault rather than as an answer to a gesture.
      return action.opened ? withDesk : { ...withDesk, sidebarOpen: state.sidebarOpen }
    }

    case "select-symbol": {
      const next: ShellState = { ...state, selected: action.selected }
      if (!action.open) return next
      return foldSidebarIfCramped({ ...next, inspector: "symbol", overlay: null })
    }

    case "context-symbol":
      return { ...state, contextSymbol: action.symbol }

    case "overlay":
      return { ...state, overlay: action.overlay }

    case "viewport":
      if (isCompact(action.width)) {
        return {
          ...state,
          viewport: action.width,
          sidebarOpen: false,
          // A pane the desk opened by itself would now be the whole screen. One
          // the reader opened deliberately is theirs to keep.
          inspector: state.inspectorPinned ? state.inspector : null,
        }
      }
      return foldSidebarIfCramped({ ...state, viewport: action.width })

    case "draft":
      return { ...state, draft: action.text }

    case "news-article":
      // An article opening is a change of what the main column reads, so
      // whatever was floating over it belongs to the screen being left.
      return { ...state, newsArticle: action.article, overlay: null }

    case "pick-attachment":
      // The composer opens the picker; this only says that it was asked for.
      // Leaving the chrome alone is deliberate — a shortcut for adding a file
      // should not also close an overlay the reader is reading.
      return { ...state, attachRequests: state.attachRequests + 1 }
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
  const [state, rawDispatch] = useReducer(reduce, INITIAL)

  // The latest state, for the dispatch wrapper. It cannot close over `state`
  // without being rebuilt on every keystroke in the composer, and every
  // consumer of `dispatch` would re-render with it.
  const latest = useRef(state)
  latest.current = state

  const dispatch = useCallback((action: Action): void => {
    if (action.type === "view") writeShellViewToHistory(action.view)
    // Only a deliberate toggle of the *column* is remembered, and only two of
    // the four things that dispatch this are one. The shell folds the sidebar
    // itself when three columns will not fit, and Escape dispatches the same
    // action to dismiss the list while it is floating — a gesture that closes
    // an overlay, not one that states a preference. Persisting either would
    // leave the sidebar shut for good after a session on a narrow window.
    if (action.type === "toggle-sidebar" && !sidebarWouldFloat(latest.current)) {
      writePreferences({ sidebarOpen: !latest.current.sidebarOpen })
    }
    rawDispatch(action)
  }, [])

  // What this browser remembered, applied once. A reader who dragged the seam
  // or shut the sidebar has already said what they want; making them say it
  // again after every reload is the shell forgetting on purpose.
  useEffect(() => {
    const saved = readPreferences()
    if (saved.sidebarOpen === null && saved.chatWidth === null) return
    rawDispatch({
      type: "restore-layout",
      sidebarOpen: saved.sidebarOpen,
      chatWidth: saved.chatWidth,
    })
  }, [])

  // The width the reader settled on, written once they have settled on it.
  // Guarded on `dragging` so a drag writes at its end rather than on every
  // frame of it, and on `null` so the automatic resets — a Thread switch, the
  // desk opening — are not mistaken for a choice.
  useEffect(() => {
    if (state.dragging || state.chatWidth === null) return
    writePreferences({ chatWidth: state.chatWidth })
  }, [state.chatWidth, state.dragging])

  useEffect(() => {
    const restore = (): void => {
      const linked = shellViewFromSearch(window.location.search)
      rawDispatch({ type: "view", view: linked ?? "chat" })
    }
    restore()
    window.addEventListener("popstate", restore)
    return () => window.removeEventListener("popstate", restore)
  }, [])

  // Measured after mount rather than read during render: `window` does not
  // exist on the server, and seeding a guess would make the first client tree
  // disagree with the HTML it is hydrating.
  useEffect(() => {
    const measure = () => dispatch({ type: "viewport", width: window.innerWidth })
    measure()
    window.addEventListener("resize", measure)
    return () => window.removeEventListener("resize", measure)
  }, [dispatch])

  // Escape closes whatever floats; ⌘K / Ctrl+K opens the palette and ⇧⌘, the
  // settings dialog, from anywhere.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        // One press, one layer. An overlay floating over the desk is what the
        // reader is looking at, so Escape takes only that; a second press
        // reaches the pane under it.
        if (state.overlay !== null) {
          dispatch({ type: "overlay", overlay: null })
        } else if (state.inspector !== null) {
          dispatch({ type: "close-inspector" })
        }
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        // One shortcut, aimed at whichever list the reader is standing in. With
        // the workspace open the thing there are twenty of is boards, not
        // conversations, and making them reach for a second chord to say so
        // would put the more common search behind the rarer one.
        dispatch({
          type: "overlay",
          overlay: state.inspector === "deskView" ? "boards" : "palette",
        })
      }
      // The hint is printed on the menu row (`composer.tsx`), and a printed
      // shortcut that does nothing is the same broken promise this whole
      // change is clearing up. It lives in this listener rather than in a
      // second one because the composer's only `keydown` is on its textarea,
      // and ⌘U has to work while the focus is anywhere.
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "u") {
        event.preventDefault()
        dispatch({ type: "pick-attachment" })
      }
      // Matched on `code` rather than `key`: with Shift held the comma key
      // reports ">" on a US layout and something else again on every other one.
      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.code === "Comma") {
        event.preventDefault()
        dispatch({ type: "overlay", overlay: "settings" })
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [dispatch, state.inspector, state.overlay])

  const value = useMemo<ShellApi>(
    () => ({ state, dispatch, panelWidth: inspectorWidth(state) }),
    [dispatch, state],
  )

  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>
}

/**
 * The shell as it was a moment ago, for a surface on its way out.
 *
 * A pane that slides shut over 420ms is drawn for 420ms after the state that
 * opened it has gone: `inspector` is null, `panelWidth` is zero, and every child
 * reading `useShell` would redraw itself for a closed desk while still on
 * screen — the sources tab falling back to the board, the board to its empty
 * line. Handing the subtree the last open value instead keeps the picture still
 * for the length of the slide. `dispatch` stays live; the pane itself turns
 * pointer events off.
 */
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

/**
 * Dragging the seam between the conversation and the Signal Desk.
 *
 * What moves is the **chat column**: the pane takes whatever is left, so a
 * handle that widened the pane and a handle that narrowed the chat would be two
 * names for one gesture, and only one of them survives the sidebar folding
 * underneath it.
 *
 * Pointer events rather than mouse events, so a trackpad, a pen and a touch
 * screen all resize the same way. Listeners go on the window because the
 * pointer leaves the 1px handle almost immediately.
 */
export function useChatColumnDrag() {
  const { state, dispatch } = useShell()
  const startWidth = chatColumnWidth(state)

  return useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      const startX = event.clientX
      dispatch({ type: "dragging", dragging: true })

      // The seam is the chat column's right edge, so it widens as the pointer
      // travels right.
      const move = (moved: PointerEvent) =>
        dispatch({ type: "resize-chat", width: startWidth + (moved.clientX - startX) })

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
    [dispatch, startWidth],
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
