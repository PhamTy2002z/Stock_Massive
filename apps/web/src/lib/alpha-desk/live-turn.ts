/**
 * The live Turn's own state, and the rules for advancing it.
 *
 * A **dedicated reducer**, not per-block writes into TanStack Query
 * (ADR-0013). Query keeps every canonical resource — Threads, messages, the
 * rail — and at a terminal event the surface refetches the Thread and replaces
 * this draft with the canonical message. Writing each block into the cache
 * instead would make a Turn in flight indistinguishable from a Thread that had
 * been saved, and a reload mid-Turn would show half an answer as history.
 *
 * Three rules, and they are the whole of the replay contract:
 *
 * **A duplicate is ignored.** `seq` is monotonic per Turn, so an event at or
 * below the highest applied has already been applied. Reconnecting mid-Turn
 * genuinely does redeliver, because a snapshot restates rather than replays.
 *
 * **A gap is not patched over.** An event more than one past the highest
 * applied means something was missed, and there is no way to reconstruct it
 * from what is here. The state says so and the connection is restarted for a
 * fresh snapshot; guessing would leave a hole nobody could see.
 *
 * **A snapshot replaces, it does not merge.** It is the current state of the
 * answer, complete, and merging it into what is already on screen would
 * duplicate every block on every reconnect.
 *
 * Pure, and separate from the hook that feeds it, because every one of those
 * rules is a statement about a sequence of events rather than about React.
 */

import {
  isTerminalEvent,
  type ActivityPhase,
  type ContentBlock,
  type SnapshotData,
  type TurnEvent,
  type WidgetSpec,
} from "./types"

/**
 * Where a Turn is, as the surface needs to render it.
 *
 * The four terminal meanings each get their own value, because the UI treats
 * them differently and must never collapse them: `incomplete` keeps its useful
 * content and offers retry, where `failed` is the one that has nothing to keep.
 */
export type LivePhase =
  | "idle"
  | "starting"
  | "running"
  | "cancelling"
  | "completed"
  | "incomplete"
  | "failed"
  | "cancelled"

export interface LiveTurn {
  turnId: string | null
  threadId: string | null
  phase: LivePhase
  /** The highest `seq` applied. Also what a duplicate is measured against. */
  seq: number
  activity: ActivityPhase | null
  blocks: ContentBlock[]
  widgets: WidgetSpec[]
  terminalReason: string | null
  /** The canonical assistant message id, once the terminal event names one. */
  messageId: number | null
  /**
   * A gap was seen. The hook reopens the stream, which answers with a fresh
   * snapshot; nothing else clears it, because nothing else can.
   */
  needsResync: boolean
}

export const IDLE: LiveTurn = {
  turnId: null,
  threadId: null,
  phase: "idle",
  seq: 0,
  activity: null,
  blocks: [],
  widgets: [],
  terminalReason: null,
  messageId: null,
  needsResync: false,
}

export type LiveTurnAction =
  | { type: "start"; turnId: string; threadId: string }
  | { type: "event"; event: TurnEvent }
  | { type: "cancelling" }
  | { type: "resynced" }
  | { type: "reset" }
  // A frame the client could not parse. Indistinguishable from a missed one in
  // every way that matters, so it takes the same route.
  | { type: "gap" }
  // How the Turn ended, read from the Turn row rather than from the stream.
  // The sequence rules deliberately do not apply: this is the authoritative
  // answer arriving *because* the stream stopped giving one, and holding it to
  // a contract about stream ordering would leave the surface spinning on a
  // Turn that has already finished.
  | {
      type: "settled"
      status: "complete" | "incomplete" | "cancelled"
      terminalReason: string | null
      messageId: number | null
    }

const TERMINAL_PHASE: Record<string, LivePhase> = {
  "turn.completed": "completed",
  "turn.incomplete": "incomplete",
  "turn.failed": "failed",
  "turn.cancelled": "cancelled",
}

export function liveTurnReducer(state: LiveTurn, action: LiveTurnAction): LiveTurn {
  switch (action.type) {
    case "start":
      // A new Turn starts from nothing. The previous one is already in the
      // transcript as a canonical message, so keeping its blocks here would
      // show them twice.
      return {
        ...IDLE,
        turnId: action.turnId,
        threadId: action.threadId,
        phase: "starting",
      }

    case "cancelling":
      // Immediate in the UI, and it keeps every block already received. The
      // terminal event decides how the Turn actually ended.
      return state.phase === "starting" || state.phase === "running"
        ? { ...state, phase: "cancelling" }
        : state

    case "resynced":
      return state.needsResync ? { ...state, needsResync: false } : state

    case "gap":
      return state.turnId === null ? state : { ...state, needsResync: true }

    case "settled":
      return isSettled(state)
        ? state
        : {
            ...state,
            phase: phaseForStatus(action.status, state.blocks.length > 0),
            activity: null,
            terminalReason: action.terminalReason,
            messageId: action.messageId,
            needsResync: false,
          }

    case "reset":
      return IDLE

    case "event":
      return applyEvent(state, action.event)
  }
}

function applyEvent(state: LiveTurn, event: TurnEvent): LiveTurn {
  if (state.turnId !== null && event.turn_id !== state.turnId) {
    // An event from a Turn this reducer is not showing. Possible for exactly
    // one instant after a retry, while the old stream is still closing.
    return state
  }

  if (event.type === "turn.snapshot") return fromSnapshot(state, event)

  if (event.seq <= state.seq) return state // a duplicate; already applied
  if (event.seq > state.seq + 1) {
    // A gap. Nothing here can reconstruct the missing event, so the state says
    // so and the connection is restarted rather than the hole being hidden.
    return { ...state, needsResync: true }
  }

  const advanced = { ...state, seq: event.seq }

  switch (event.type) {
    case "turn.activity":
      return { ...advanced, activity: (event.data.phase as ActivityPhase) ?? null }

    case "content.block":
      return {
        ...advanced,
        // The activity line belongs to work in progress; a block arriving is
        // that work having produced something.
        activity: null,
        blocks: [...advanced.blocks, event.data.block as ContentBlock],
      }

    case "widget.ready":
      return { ...advanced, widgets: [...advanced.widgets, event.data.widget as WidgetSpec] }

    default:
      return isTerminalEvent(event.type)
        ? {
            ...advanced,
            phase: TERMINAL_PHASE[event.type],
            activity: null,
            terminalReason: (event.data.terminal_reason as string | null) ?? null,
            messageId: (event.data.message_id as number | null) ?? null,
          }
        : advanced
  }
}

function fromSnapshot(state: LiveTurn, event: TurnEvent): LiveTurn {
  const data = event.data as unknown as SnapshotData
  const terminal = data.status !== "admitted" && data.status !== "running"
  return {
    ...state,
    turnId: event.turn_id,
    // Replaced wholesale. A snapshot is the current state of the answer, and
    // merging it would duplicate every block on every reconnect.
    seq: data.through_seq,
    activity: data.activity ?? null,
    blocks: [...data.blocks],
    widgets: [...data.widgets],
    terminalReason: data.terminal_reason ?? null,
    needsResync: false,
    phase: terminal
      ? phaseForStatus(data.status, data.blocks.length > 0)
      : keepCancelling(state.phase),
  }
}

/**
 * Which terminal phase a snapshot's status means.
 *
 * `incomplete` splits the same way the backend's terminal event does, and for
 * the same reason: the UI must never replace useful content with a full-screen
 * error, so an incomplete Turn with blocks is a partial answer and one without
 * is the failure.
 */
function phaseForStatus(
  status: SnapshotData["status"] | "complete" | "incomplete" | "cancelled",
  hasContent: boolean,
): LivePhase {
  if (status === "complete") return "completed"
  if (status === "cancelled") return "cancelled"
  return hasContent ? "incomplete" : "failed"
}

function keepCancelling(phase: LivePhase): LivePhase {
  // A snapshot arriving mid-cancel says the Turn is still running, which is
  // true and not what the user should be shown: they pressed stop, and the
  // control stays disabled until the Turn actually ends.
  return phase === "cancelling" ? "cancelling" : "running"
}

/** Whether the Turn has reached one of the four terminal meanings. */
export function isSettled(state: LiveTurn): boolean {
  return (
    state.phase === "completed" ||
    state.phase === "incomplete" ||
    state.phase === "failed" ||
    state.phase === "cancelled"
  )
}

/** Whether the composer's stop control should be live. */
export function isActive(state: LiveTurn): boolean {
  return state.phase === "starting" || state.phase === "running"
}
