"use client"

import { useCallback, useEffect, useReducer, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { AlphaRefusalError } from "@/lib/alpha"
import {
  cancelTurn,
  createTurn,
  fetchTurn,
  newTurnId,
  turnStreamUrl,
  type CreateTurnInput,
} from "@/lib/alpha-desk/api"
import { announceSettledTurn } from "@/lib/alpha-desk/answer-alert"
import {
  IDLE,
  isActive,
  isSettled,
  liveTurnReducer,
  type LiveTurn,
  type LiveTurnAction,
} from "@/lib/alpha-desk/live-turn"
import type { Thread, Turn, TurnEvent, TurnEventType } from "@/lib/alpha-desk/types"
import { ApiUnavailableError, isRetryableStatus } from "@/lib/connection-status"
import { queryKeys } from "@/lib/query-keys"

/**
 * One live Turn: admit it, watch it, cancel it, and hand it over at the end.
 *
 * The reducer owns the draft and TanStack Query owns everything canonical. At a
 * terminal event this refetches the Thread; the surface then replaces the draft
 * with the message that came back. Nothing here writes the answer into the
 * query cache, because a Turn in flight is not history yet.
 *
 * **Reattaching is not restarting.** A page reload, a route change or a dropped
 * network ends a subscriber and nothing else: the Turn belongs to the backend,
 * so opening an `EventSource` on a `turnId` picks it up wherever it got to.
 * `EventSource` reconnects natively with `Last-Event-ID`, and the snapshot that
 * answers replaces the projection outright.
 */

// Every type the stream can carry. Listed because the backend names its events,
// and a named SSE event never fires the default `message` handler.
const EVENT_TYPES: TurnEventType[] = [
  "turn.snapshot",
  "content.delta",
  "tool.call",
  "part.progress",
  "part.question",
  "turn.completed",
  "turn.incomplete",
  "turn.failed",
  "turn.cancelled",
]

// How long to wait after a stream error before asking the backend what actually
// happened. Long enough that the browser's own reconnection (about three
// seconds) gets to try first, so an ordinary blip costs no request at all.
const ERROR_PROBE_MS = 4000

// When the probe itself cannot reach the backend — a restart, a 503, a session
// being rotated — it asks again on a widening interval rather than giving up,
// because giving up is what left a finished Turn spinning forever.
const PROBE_BACKOFF_MS = 2000
const PROBE_BACKOFF_MAX_MS = 30_000

/** How long to wait before the next probe, after this many failed ones. */
export function probeBackoffMs(failures: number): number {
  return Math.min(PROBE_BACKOFF_MS * 2 ** failures, PROBE_BACKOFF_MAX_MS)
}

// A create whose answer was lost may still have committed. Bounded, because a
// reader pressed Send once and is waiting on the outcome of that press.
const ADMIT_RETRIES = 2
const ADMIT_BACKOFF_MS = 1000

/** What the composer hands over: the question, and the mode it was asked in. */
export interface TurnInput {
  text: string
  symbols?: string[]
  /** The Signal Desk switch as it stood when the question was sent. */
  signalDesk?: boolean
  /**
   * The attachments this question carries, by id.
   *
   * Ids and not files: they were uploaded when the reader chose them, so this
   * stays a small JSON request and stays idempotent.
   */
  attachments?: string[]
  /**
   * The Thread to ask in, when it is not the one this hook was given.
   *
   * The first question of a new conversation names the Thread its create just
   * returned. Reading the open Thread instead would send it wherever the reader
   * had clicked in the meantime.
   */
  threadId?: string
}

export interface LiveTurnController {
  state: LiveTurn
  /** Admit a Turn under an id generated here, before the request goes out. */
  send: (input: TurnInput) => Promise<void>
  /** Immediate in the UI, and it keeps every word already received. */
  cancel: () => Promise<void>
  /** A new Turn pointing at the old one. The previous Turn stays untouched. */
  retry: (input: TurnInput) => Promise<void>
  /** The admission refusal, when the last create was refused. */
  refusal: Error | null
  clearRefusal: () => void
  reset: () => void
  /** Reattach to a Turn this browser did not start in this mount. */
  attach: (turnId: string, threadId: string) => void
}

export function useLiveTurn(threadId: string | null): LiveTurnController {
  const [state, dispatch] = useReducer(liveTurnReducer, IDLE)
  const [refusal, setRefusal] = useState<Error | null>(null)
  // Bumped to force a fresh connection: a gap has to be answered by a new
  // snapshot, and only a new connection produces one.
  const [attempt, setAttempt] = useState(0)
  const queryClient = useQueryClient()
  // The state as of the last render, for the actions below that must know what
  // they are replacing without re-creating themselves on every event.
  const stateRef = useRef(state)
  stateRef.current = state

  const turnId = state.turnId
  const subscribable = state.subscribable
  const settled = isSettled(state)
  const active = isActive(state) || state.phase === "cancelling"

  // -- the stream ---------------------------------------------------------

  useEffect(() => {
    // Not before the backend has a Turn under this id. `EventSource` fails the
    // connection on a non-200 rather than retrying, so a subscribe that raced
    // the create would leave this tab watching a stream that never speaks.
    if (!turnId || settled || !subscribable) return

    const source = new EventSource(turnStreamUrl(turnId))
    let timer: ReturnType<typeof setTimeout> | undefined
    // One probe chain at a time, from the first error until it has an answer.
    // `EventSource` reports an error on every reconnect attempt, and a second
    // chain would only ask the same question twice as often.
    let probing = false
    let failures = 0
    let closed = false

    const stopProbing = () => {
      if (timer) clearTimeout(timer)
      timer = undefined
      probing = false
    }

    const probe = async () => {
      timer = undefined
      const outcome = await settleFromServer(turnId, dispatch)
      if (closed || !probing) return
      if (outcome === "unreachable") {
        timer = setTimeout(() => void probe(), probeBackoffMs(failures))
        failures += 1
        return
      }
      probing = false
      // A Turn that is still running means the connection failed rather than
      // the Turn ending, so this reopens it. `EventSource` retries a dropped
      // connection itself but gives up on a refused one, and the two are the
      // same thing to a reader watching an answer that stopped arriving.
      if (outcome === "running") setAttempt((previous) => previous + 1)
    }

    const onEvent = (message: MessageEvent<string>) => {
      // The stream is speaking again, so whatever the probe was about to ask
      // has been answered.
      stopProbing()
      try {
        dispatch({ type: "event", event: JSON.parse(message.data) as TurnEvent })
      } catch {
        // A frame this client cannot parse is a frame it cannot apply, which
        // is a gap by any other name.
        dispatch({ type: "gap" })
      }
    }

    const onError = () => {
      // `EventSource` reports an error for an ordinary reconnect as well as for
      // a Turn that has gone away, and it retries either way. Rather than guess,
      // ask the backend — and keep asking, further apart, while it cannot
      // answer. A Turn that ended while the connection was down must not leave
      // the UI spinning on a stream that will never speak.
      if (probing) return
      probing = true
      failures = 0
      timer = setTimeout(() => void probe(), ERROR_PROBE_MS)
    }

    for (const type of EVENT_TYPES) source.addEventListener(type, onEvent as EventListener)
    source.addEventListener("error", onError)

    return () => {
      closed = true
      stopProbing()
      for (const type of EVENT_TYPES) source.removeEventListener(type, onEvent as EventListener)
      source.removeEventListener("error", onError)
      source.close()
    }
  }, [turnId, settled, subscribable, attempt])

  // A gap forces a fresh snapshot, and a fresh snapshot needs a fresh
  // connection. Clearing the flag first keeps this from firing twice.
  useEffect(() => {
    if (!state.needsResync) return
    dispatch({ type: "resynced" })
    setAttempt((previous) => previous + 1)
  }, [state.needsResync])

  // -- handing the Turn over ---------------------------------------------

  const settledThreadId = settled ? state.threadId : null
  useEffect(() => {
    if (!settledThreadId) return
    // The terminal event is published *after* the terminal transaction commits,
    // so the message this refetch is looking for is already there.
    void queryClient.invalidateQueries({ queryKey: queryKeys.thread(settledThreadId) })
    // A Turn can have touched a symbol the rail cares about.
    void queryClient.invalidateQueries({ queryKey: queryKeys.threads })
  }, [settledThreadId, state.phase, queryClient])

  // -- telling a reader who looked away ------------------------------------

  // Only a Turn this mount watched running is announced. A reload that
  // reattaches to a Turn which ended while nobody was looking settles on its
  // first snapshot, and announcing that would be news the reader already has.
  const watched = useRef<string | null>(null)
  useEffect(() => {
    if (turnId && active) watched.current = turnId
  }, [turnId, active])
  const phase = state.phase
  useEffect(() => {
    if (!settled || !turnId || watched.current !== turnId) return
    watched.current = null
    // A cancel is the reader's own act; there is nothing to come back for.
    if (phase === "cancelled") return
    const thread = queryClient
      .getQueryData<{ threads: Thread[] }>(queryKeys.threads)
      ?.threads.find((row) => row.id === state.threadId)
    announceSettledTurn({ turnId, title: thread?.title ?? null, answered: phase !== "failed" })
  }, [settled, turnId, phase, state.threadId, queryClient])

  // -- the three actions --------------------------------------------------

  const start = useCallback(
    async (input: TurnInput, retryOfTurnId: string | null) => {
      const target = input.threadId ?? threadId
      if (!target) return
      // Generated before the request, so a retried admission on a flaky network
      // resolves to the same Turn instead of starting a second one.
      const id = newTurnId()
      // A Turn still running in another Thread, which this one is about to
      // take the screen from. Its Thread is marked stale now, because nothing
      // will be watching for its terminal event to refetch it.
      const previous = stateRef.current
      const displaced =
        previous.turnId !== null &&
        previous.threadId !== null &&
        (isActive(previous) || previous.phase === "cancelling")
          ? { turnId: previous.turnId, threadId: previous.threadId }
          : null
      if (displaced) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.thread(displaced.threadId) })
      }
      setRefusal(null)
      dispatch({ type: "start", turnId: id, threadId: target })
      try {
        await admitTurn({
          threadId: target,
          turnId: id,
          text: input.text,
          attachments: input.attachments ?? [],
          symbols: input.symbols,
          signalDesk: input.signalDesk,
          retryOfTurnId,
        })
      } catch (error) {
        // An admission refusal is an HTTP outcome, never an event. The draft is
        // dropped because there is no Turn behind it.
        dispatch({ type: "reset" })
        // The refusal is usually that Turn still holding the account's one
        // active slot, so it goes back on the screen it was taken from.
        if (displaced) dispatch({ type: "start", ...displaced, subscribable: true })
        setRefusal(error instanceof Error ? error : new Error(String(error)))
        return
      }
      // The Turn exists now, so the stream may open on it.
      dispatch({ type: "admitted" })
      // The user message is committed by the time the create returns, so the
      // transcript can show it without an optimistic copy that might not match.
      void queryClient.invalidateQueries({ queryKey: queryKeys.thread(target) })
      // The same commit names an unnamed Thread after the question that opened
      // it, so the list is refetched now rather than at the terminal event —
      // the sidebar would otherwise show the timestamped fallback for as long
      // as the answer takes.
      void queryClient.invalidateQueries({ queryKey: queryKeys.threads })
    },
    [threadId, queryClient],
  )

  const send = useCallback((input: TurnInput) => start(input, null), [start])

  const retry = useCallback(
    // A retry is a new Turn carrying `retry_of_turn_id`; the previous Turn, its
    // spend, its message and its traces stay immutable. Only a Turn of the
    // Thread being asked in can be the one retried.
    (input: TurnInput) =>
      start(input, state.threadId === (input.threadId ?? threadId) ? state.turnId : null),
    [start, state.turnId, state.threadId, threadId],
  )

  const cancel = useCallback(async () => {
    if (!turnId || !active) return
    dispatch({ type: "cancelling" })
    try {
      // A Turn that had already ended answers with its ending, and the stream
      // that would have said so may be the thing that stopped working.
      const action = settledAction(await cancelTurn(turnId))
      if (action) dispatch(action)
    } catch {
      // Idempotent upstream, and the terminal event is what actually settles
      // the Turn. A failed cancel leaves the UI honest rather than stuck.
    }
  }, [turnId, active])

  const attach = useCallback((id: string, thread: string) => {
    // Reattaching, so the Turn already exists and the stream may open at once.
    dispatch({ type: "start", turnId: id, threadId: thread, subscribable: true })
  }, [])

  return {
    state,
    send,
    cancel,
    retry,
    refusal,
    clearRefusal: useCallback(() => setRefusal(null), []),
    reset: useCallback(() => dispatch({ type: "reset" }), []),
    attach,
  }
}

/** The ending a Turn row records, or null while it is still running. */
function settledAction(turn: Turn): LiveTurnAction | null {
  if (turn.status === "admitted" || turn.status === "running") return null
  return {
    type: "settled",
    turnId: turn.id,
    status: turn.status,
    terminalReason: turn.terminal_reason,
    messageId: turn.response_message_id,
  }
}

/**
 * A request whose answer never arrived, as opposed to one that was refused.
 *
 * A `401` counts: the proxy has already tried to rotate the session, and one
 * that could not be rotated this second is often a restart racing the cookie.
 */
function unreachable(error: unknown): boolean {
  if (error instanceof ApiUnavailableError || error instanceof TypeError) return true
  return (
    error instanceof AlphaRefusalError &&
    (error.status === 401 || isRetryableStatus(error.status))
  )
}

/**
 * Ask the backend how a Turn ended, when the stream stopped saying.
 *
 * Synthesised into the same terminal event the stream would have carried, so
 * the reducer has exactly one way to settle rather than two.
 *
 * `running` is the caller's cue to reopen the stream rather than keep waiting
 * on one that has stopped; `unreachable` is its cue to ask again later.
 */
async function settleFromServer(
  turnId: string,
  dispatch: (action: LiveTurnAction) => void,
): Promise<"running" | "settled" | "unreachable" | "gone"> {
  try {
    const action = settledAction(await fetchTurn(turnId))
    if (action === null) return "running"
    dispatch(action)
    return "settled"
  } catch (error) {
    if (unreachable(error)) return "unreachable"
    // The Turn is gone. The surface keeps what it has rather than replacing a
    // partial answer with an error.
    return "gone"
  }
}

/**
 * Create a Turn, and survive losing the answer to that request.
 *
 * The id is the idempotency key, but admission is checked before the key is:
 * re-sending a create that did commit meets the account's one-active-Turn
 * ceiling held by that very Turn. So a lost answer is followed by asking for the
 * Turn by id, and only a Turn that is not there is created again — under the
 * same id, so a create that commits twice still names one Turn.
 */
async function admitTurn(input: CreateTurnInput): Promise<void> {
  for (let attempt = 0; ; attempt += 1) {
    try {
      await createTurn(input)
      return
    } catch (error) {
      if (!unreachableCreate(error) || attempt >= ADMIT_RETRIES) throw error
    }
    await new Promise((resolve) => setTimeout(resolve, ADMIT_BACKOFF_MS * 2 ** attempt))
    try {
      await fetchTurn(input.turnId)
      return // the lost create committed
    } catch (probe) {
      const missing = probe instanceof AlphaRefusalError && probe.status === 404
      if (!missing && !unreachableCreate(probe)) throw probe
    }
  }
}

/** A create that may or may not have reached the backend. */
function unreachableCreate(error: unknown): boolean {
  return error instanceof ApiUnavailableError || error instanceof TypeError
}
