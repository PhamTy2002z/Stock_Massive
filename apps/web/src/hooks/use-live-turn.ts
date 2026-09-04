"use client"

import { useCallback, useEffect, useReducer, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

import {
  cancelTurn,
  createTurn,
  fetchTurn,
  newTurnId,
  turnStreamUrl,
} from "@/lib/alpha-desk/api"
import {
  IDLE,
  isActive,
  isSettled,
  liveTurnReducer,
  type LiveTurn,
  type LiveTurnAction,
} from "@/lib/alpha-desk/live-turn"
import type { TurnEvent, TurnEventType } from "@/lib/alpha-desk/types"
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
    let probe: ReturnType<typeof setTimeout> | undefined

    const onEvent = (message: MessageEvent<string>) => {
      if (probe) {
        clearTimeout(probe)
        probe = undefined
      }
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
      // ask the backend once — a Turn that ended while the connection was down
      // must not leave the UI spinning on a stream that will never speak.
      if (probe) return
      probe = setTimeout(() => {
        probe = undefined
        // A Turn that is still running means the connection failed rather than
        // the Turn ending, so this reopens it. `EventSource` retries a dropped
        // connection itself but gives up on a refused one, and the two are the
        // same thing to a reader watching an answer that stopped arriving.
        void settleFromServer(turnId, dispatch).then((running) => {
          if (running) setAttempt((previous) => previous + 1)
        })
      }, ERROR_PROBE_MS)
    }

    for (const type of EVENT_TYPES) source.addEventListener(type, onEvent as EventListener)
    source.addEventListener("error", onError)

    return () => {
      if (probe) clearTimeout(probe)
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

  // -- the three actions --------------------------------------------------

  const start = useCallback(
    async (input: TurnInput, retryOfTurnId: string | null) => {
      if (!threadId) return
      // Generated before the request, so a retried admission on a flaky network
      // resolves to the same Turn instead of starting a second one.
      const id = newTurnId()
      setRefusal(null)
      dispatch({ type: "start", turnId: id, threadId })
      try {
        await createTurn({
          threadId,
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
        setRefusal(error instanceof Error ? error : new Error(String(error)))
        return
      }
      // The Turn exists now, so the stream may open on it.
      dispatch({ type: "admitted" })
      // The user message is committed by the time the create returns, so the
      // transcript can show it without an optimistic copy that might not match.
      void queryClient.invalidateQueries({ queryKey: queryKeys.thread(threadId) })
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
    // spend, its message and its traces stay immutable.
    (input: TurnInput) => start(input, state.turnId),
    [start, state.turnId],
  )

  const cancel = useCallback(async () => {
    if (!turnId || !active) return
    dispatch({ type: "cancelling" })
    try {
      await cancelTurn(turnId)
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

/**
 * Ask the backend how a Turn ended, when the stream stopped saying.
 *
 * Synthesised into the same terminal event the stream would have carried, so
 * the reducer has exactly one way to settle rather than two.
 *
 * Returns whether the Turn is still running, which is the caller's cue to
 * reopen the stream rather than keep waiting on one that has stopped.
 */
async function settleFromServer(
  turnId: string,
  dispatch: (action: LiveTurnAction) => void,
): Promise<boolean> {
  try {
    const turn = await fetchTurn(turnId)
    if (turn.status === "admitted" || turn.status === "running") return true
    dispatch({
      type: "settled",
      status: turn.status,
      terminalReason: turn.terminal_reason,
      messageId: turn.response_message_id,
    })
    return false
  } catch {
    // The Turn is unreachable — signed out, or gone. The surface keeps what it
    // has rather than replacing a partial answer with an error.
    return false
  }
}
