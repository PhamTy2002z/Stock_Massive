/**
 * The live Turn's own state, and the rules for advancing it.
 *
 * A **dedicated reducer**, not per-delta writes into TanStack Query. Query
 * keeps every canonical resource — Threads, messages, the rail — and at a
 * terminal event the surface refetches the Thread and replaces this draft with
 * the canonical message. Writing the answer into the cache as it arrives would
 * make a Turn in flight indistinguishable from a Thread that had been saved,
 * and a reload mid-Turn would show half an answer as history.
 *
 * Three rules, and they are the whole of the replay contract:
 *
 * **A duplicate is ignored.** `seq` is monotonic per Turn, so an event at or
 * below the highest applied has already been applied. Reconnecting mid-Turn
 * genuinely does redeliver, because a snapshot restates rather than replays.
 *
 * **A gap is not patched over.** An event more than one past the highest
 * applied means something was missed, and there is no way to reconstruct it
 * from what is here — a missed `content.delta` is a hole in a sentence. The
 * state says so and the connection is restarted for a fresh snapshot; guessing
 * would leave a hole nobody could see.
 *
 * **A snapshot replaces, it does not merge.** It carries the whole answer so
 * far, so appending it to what is on screen would print every sentence twice
 * on every reconnect.
 *
 * Pure, and separate from the hook that feeds it, because every one of those
 * rules is a statement about a sequence of events rather than about React.
 */

import type { SnapshotData, ToolCall, TurnEvent, TurnEventType } from "./types"

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
  /**
   * The answer as far as it has arrived, deltas already joined.
   *
   * One string rather than the list of deltas that built it: a delta is a
   * transport unit and may end mid-word, so anything that rendered them
   * separately would put a boundary on screen where the answer has none.
   */
  text: string
  /**
   * The tool calls this Turn has made, in the order they first appeared.
   *
   * Keyed by id and updated in place, because a call announces itself twice —
   * once running and once with its outcome — and the second announcement is
   * the same call rather than another one.
   */
  toolCalls: ToolCall[]
  terminalReason: string | null
  /** The canonical assistant message id, once the transport names one. */
  messageId: number | null
  /**
   * A gap was seen. The hook reopens the stream, which answers with a fresh
   * snapshot; nothing else clears it, because nothing else can.
   */
  needsResync: boolean
  /**
   * Whether a subscriber may open a stream on this id yet.
   *
   * False between generating the id and the create coming back. The id is the
   * client's — it is the idempotency key, so it exists before the request — and
   * subscribing to it early gets a `404`, which `EventSource` treats as failing
   * the connection rather than as something to retry. The tab would then sit on
   * a stream that will never speak, for a Turn that is running perfectly well.
   *
   * True from the start when reattaching: that Turn already exists, and waiting
   * for an admission nobody is going to send would strand the reader.
   */
  subscribable: boolean
}

export const IDLE: LiveTurn = {
  turnId: null,
  threadId: null,
  phase: "idle",
  seq: 0,
  text: "",
  toolCalls: [],
  terminalReason: null,
  messageId: null,
  needsResync: false,
  subscribable: false,
}

export type LiveTurnAction =
  // `subscribable` is true only for a reattach, where the Turn already exists.
  | { type: "start"; turnId: string; threadId: string; subscribable?: boolean }
  // The create came back: this id now names a Turn the backend will serve.
  | { type: "admitted" }
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

/**
 * The four terminal event types, and the phase each one means.
 *
 * Also the only list of them this module keeps: asking whether an event is
 * terminal and asking what it means are the same question, so a lookup that
 * misses answers both at once. Two lists could disagree, and the one that
 * disagreed would leave a finished Turn rendering as a running one.
 */
const TERMINAL_PHASE: Partial<Record<TurnEventType, LivePhase>> = {
  "turn.completed": "completed",
  "turn.incomplete": "incomplete",
  "turn.failed": "failed",
  "turn.cancelled": "cancelled",
}

export function liveTurnReducer(state: LiveTurn, action: LiveTurnAction): LiveTurn {
  switch (action.type) {
    case "start":
      // A new Turn starts from nothing. The previous one is already in the
      // transcript as a canonical message, so keeping its text here would
      // show it twice.
      return {
        ...IDLE,
        turnId: action.turnId,
        threadId: action.threadId,
        phase: "starting",
        subscribable: action.subscribable ?? false,
      }

    case "admitted":
      return state.turnId === null ? state : { ...state, subscribable: true }

    case "cancelling":
      // Immediate in the UI, and it keeps every word already received. The
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
            phase: phaseForStatus(action.status, state.text.length > 0),
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
    case "content.delta": {
      const delta = typeof event.data.text === "string" ? event.data.text : ""
      return delta === "" ? advanced : { ...advanced, text: advanced.text + delta }
    }

    case "tool.call": {
      const call = toolCallOf(event.data)
      return call === null ? advanced : { ...advanced, toolCalls: upsert(state.toolCalls, call) }
    }

    default: {
      const phase = TERMINAL_PHASE[event.type]
      return phase === undefined
        ? advanced
        : {
            ...advanced,
            phase,
            terminalReason: (event.data.terminal_reason as string | null) ?? null,
            messageId: (event.data.message_id as number | null) ?? null,
          }
    }
  }
}

/**
 * One tool call out of an event payload, or nothing.
 *
 * An event with no id names no call, and a call with no id cannot be updated by
 * the announcement that follows it — so it is dropped rather than added as a
 * row that would then be duplicated. `summary` falls back to the tool's own
 * name, which is the one label always present.
 */
function toolCallOf(data: Record<string, unknown>): ToolCall | null {
  const id = typeof data.id === "string" ? data.id : ""
  if (id === "") return null
  const name = typeof data.name === "string" ? data.name : ""
  const status = data.status
  return {
    id,
    name,
    status: status === "ok" || status === "error" ? status : "running",
    summary: typeof data.summary === "string" && data.summary !== "" ? data.summary : name,
  }
}

/** The list with this call in it: replaced where it already is, appended otherwise. */
function upsert(calls: ToolCall[], call: ToolCall): ToolCall[] {
  const index = calls.findIndex((existing) => existing.id === call.id)
  if (index === -1) return [...calls, call]
  const next = [...calls]
  next[index] = call
  return next
}

function fromSnapshot(state: LiveTurn, event: TurnEvent): LiveTurn {
  const data = event.data as unknown as SnapshotData
  const terminal = data.status !== "admitted" && data.status !== "running"
  const text = typeof data.text === "string" ? data.text : ""
  return {
    ...state,
    turnId: event.turn_id,
    // Replaced wholesale. A snapshot is the answer as it stands, and merging it
    // would print every sentence twice on every reconnect.
    seq: data.through_seq,
    text,
    toolCalls: Array.isArray(data.tool_calls) ? [...data.tool_calls] : [],
    terminalReason: data.terminal_reason ?? null,
    // A terminal snapshot names the message that replaces this draft, exactly
    // as the terminal event does. Without it a reader arriving after the Turn
    // ended would hold a draft it could never hand over, and show the answer
    // twice.
    messageId: data.message_id ?? state.messageId,
    needsResync: false,
    phase: terminal ? phaseForStatus(data.status, text.length > 0) : keepCancelling(state.phase),
  }
}

/**
 * Which terminal phase a snapshot's status means.
 *
 * `incomplete` splits the same way the backend's terminal event does, and for
 * the same reason: the UI must never replace useful content with a full-screen
 * error, so an incomplete Turn that said something is a partial answer and one
 * that said nothing is the failure.
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

/**
 * What "ask this again" means for one question in the transcript.
 *
 * Three answers, and the distinction between the first two is what a Turn id
 * records. Asking the *last* question again after its Turn hung, failed or was
 * cancelled is a second attempt, and goes out with `retry_of_turn_id` so the
 * two are linked. Asking an earlier one — or the last one after it was answered
 * — is a new question that happens to repeat one, and claiming it retried a
 * Turn that already answered would make the lifecycle say something false.
 *
 * `"nothing"` while a Turn is in flight: the composer offers Stop rather than
 * Send for that stretch, and a resend slipping past it opens a second Turn
 * behind the one on screen.
 */
export function resendPlan(
  state: LiveTurn,
  isLastQuestion: boolean,
): "retry" | "submit" | "nothing" {
  if (isActive(state)) return "nothing"
  const endedBadly =
    state.phase === "failed" ||
    state.phase === "incomplete" ||
    state.phase === "cancelled"
  return isLastQuestion && endedBadly ? "retry" : "submit"
}
