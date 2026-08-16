"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"

import { WatchlistRail } from "@/components/alpha/watchlist-rail"
import { useLiveTurn } from "@/hooks/use-live-turn"
import { useCreateThread, useThread } from "@/hooks/use-threads"
import { useWatchlistRail } from "@/hooks/use-watchlist-rail"
import {
  deepLinkedSymbol,
  openingState,
  readDeskSession,
  writeDeskSession,
} from "@/lib/alpha-desk/desk-session"
import { isActive, isSettled } from "@/lib/alpha-desk/live-turn"
import { buildTranscript } from "@/lib/alpha-desk/transcript"
import { DeskSurface } from "./desk-surface"
import { HistoryMenu } from "./history-menu"
import { SymbolDock, type DockSymbol } from "./symbol-dock"

/**
 * Alpha Desk: the dock, the transcript, and the composer.
 *
 * The container, and the only place that knows about hooks. It owns three
 * things and delegates everything else:
 *
 * - **the Thread**, which is created lazily. A visit that asks nothing leaves
 *   no empty Thread behind, so the first question is what opens one;
 * - **the active lens**, which is a workspace setting and not a persistence
 *   key. Switching it starts no Thread and ends none — the conversation is
 *   free-roaming and carries whatever symbols it touched;
 * - **reattaching**, from what this tab remembered. A reload, a route change
 *   and a dropped network each end a subscriber; the Turn keeps running on the
 *   backend and is picked up wherever it got to (ADR-0013).
 */
export function AlphaDesk() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const symbolParam = searchParams.get("symbol")

  // Read once, on mount. `sessionStorage` is not reactive, and re-reading it on
  // a later render would fight the state it seeded.
  const [opening] = useState(() =>
    openingState(deepLinkedSymbol(symbolParam), readDeskSession()),
  )

  const [threadId, setThreadId] = useState<string | null>(opening.threadId)
  const [activeSymbol, setActiveSymbol] = useState<string | null>(opening.activeSymbol)
  // Sent, and the create has not committed it yet. Shown locally for exactly
  // that gap, then replaced by the copy the Thread comes back with.
  const [unconfirmedQuestion, setUnconfirmedQuestion] = useState<string | null>(null)
  // Held because there is no Thread to send it to yet. Released by the effect
  // below the moment one exists.
  const [queuedQuestion, setQueuedQuestion] = useState<string | null>(null)
  // A Thread that could not be opened. Kept separately from the Turn's own
  // refusal because it is a different failure: nothing was admitted, and there
  // is no Turn to retry.
  const [threadError, setThreadError] = useState<string | null>(null)

  const thread = useThread(threadId)
  const turn = useLiveTurn(threadId)
  const createThread = useCreateThread()
  const rail = useWatchlistRail()

  // The deep link is consumed once. Left in the URL, every later reload would
  // read as a fresh arrival, open yet another Thread, and abandon the Turn the
  // user is watching — so the parameter is dropped as soon as it is taken.
  useEffect(() => {
    if (symbolParam !== null) router.replace("/alpha-desk", { scroll: false })
  }, [symbolParam, router])

  const { attach } = turn
  const attachedOnce = useRef(false)
  useEffect(() => {
    if (attachedOnce.current) return
    attachedOnce.current = true
    if (opening.turnId && opening.threadId) attach(opening.turnId, opening.threadId)
  }, [opening.turnId, opening.threadId, attach])

  // What this tab was doing, for the next mount. A settled Turn is forgotten:
  // reattaching to it would open a stream for a Turn the transcript already
  // shows as a canonical message.
  const liveTurnId = turn.state.turnId
  const turnSettled = isSettled(turn.state)
  useEffect(() => {
    writeDeskSession({
      threadId,
      turnId: turnSettled ? null : liveTurnId,
      activeSymbol,
    })
  }, [threadId, liveTurnId, turnSettled, activeSymbol])

  // -- sending ------------------------------------------------------------

  const { send } = turn
  const submit = useCallback(
    (text: string) => {
      setUnconfirmedQuestion(text)
      setThreadError(null)
      if (threadId) {
        // `symbols` stays empty and the lens travels as `active_symbol`. They
        // are different things: the lens organises the Analysis context, and
        // guessing which symbols a sentence is *about* would put a parser in
        // the browser and a wrong answer in the idempotency payload.
        void send({ text, activeSymbol })
        return
      }
      setQueuedQuestion(text)
      createThread.mutate(undefined, {
        onSuccess: (created) => setThreadId(created.id),
        onError: (error) => {
          // Nothing stays queued behind a Thread that does not exist. Leaving
          // the question parked would disable the composer for the rest of the
          // session, waiting for a Thread that is never coming.
          setQueuedQuestion(null)
          setUnconfirmedQuestion(null)
          setThreadError(
            error instanceof Error ? error.message : "Không mở được cuộc trò chuyện.",
          )
        },
      })
    },
    [threadId, activeSymbol, send, createThread],
  )

  useEffect(() => {
    if (!threadId || queuedQuestion === null) return
    const text = queuedQuestion
    setQueuedQuestion(null)
    void send({ text, activeSymbol })
  }, [threadId, queuedQuestion, activeSymbol, send])

  // The create commits the user message before it returns, so the copy on
  // screen stops being a local one as soon as the Thread comes back.
  const messages = useMemo(() => thread.data?.messages ?? [], [thread.data])
  useEffect(() => {
    if (unconfirmedQuestion === null) return
    const last = messages[messages.length - 1]
    if (last?.role === "user" && last.content.text === unconfirmedQuestion) {
      setUnconfirmedQuestion(null)
    }
  }, [messages, unconfirmedQuestion])

  // -- what is on screen --------------------------------------------------

  const entries = useMemo(
    () =>
      buildTranscript({
        threadId,
        messages,
        live: turn.state,
        pendingUserText: unconfirmedQuestion,
      }),
    [threadId, messages, turn.state, unconfirmedQuestion],
  )

  const lastQuestion = useMemo(() => {
    for (let index = entries.length - 1; index >= 0; index -= 1) {
      const entry = entries[index]
      if (entry.kind === "user") return entry.text
    }
    return null
  }, [entries])

  const { retry } = turn
  const onRetry = useCallback(() => {
    // A new Turn pointing at the old one. The previous Turn and everything it
    // wrote stay exactly where they are.
    if (lastQuestion === null) return
    setUnconfirmedQuestion(null)
    void retry({ text: lastQuestion, activeSymbol })
  }, [lastQuestion, activeSymbol, retry])

  // -- the dock -----------------------------------------------------------

  const dockSymbols: DockSymbol[] = useMemo(
    () =>
      (rail.data?.entries ?? []).map((entry) => ({
        symbol: entry.symbol,
        state: entry.state,
        verdict: entry.latest?.verdict ?? null,
        unread: entry.unread,
      })),
    [rail.data],
  )

  const dock = (
    <SymbolDock
      symbols={dockSymbols}
      activeSymbol={activeSymbol}
      // Only the lens moves. No Thread is opened, none is closed, and nothing
      // is added to the Watchlist.
      onSelect={setActiveSymbol}
      tradingDay={rail.data?.trading_day ?? null}
      count={rail.data?.count ?? 0}
      cap={rail.data?.cap ?? 0}
    >
      <WatchlistRail />
    </SymbolDock>
  )

  const openThread = useCallback((id: string) => {
    setThreadId(id)
    setUnconfirmedQuestion(null)
    setThreadError(null)
  }, [])

  const { clearRefusal, reset } = turn
  const newThread = useCallback(() => {
    setThreadId(null)
    setUnconfirmedQuestion(null)
    setThreadError(null)
    reset()
  }, [reset])

  const dismissRefusal = useCallback(() => {
    setThreadError(null)
    clearRefusal()
  }, [clearRefusal])

  return (
    <DeskSurface
      dock={dock}
      history={
        <HistoryMenu
          currentThreadId={threadId}
          onOpenThread={openThread}
          onNewThread={newThread}
        />
      }
      entries={entries}
      activeSymbol={activeSymbol}
      canCancel={isActive(turn.state)}
      isCancelling={turn.state.phase === "cancelling"}
      isSubmitting={createThread.isPending || queuedQuestion !== null}
      refusal={turn.refusal?.message ?? threadError}
      onSend={submit}
      onCancel={turn.cancel}
      onRetry={onRetry}
      onDismissRefusal={dismissRefusal}
    />
  )
}
