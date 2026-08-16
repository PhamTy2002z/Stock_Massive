"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { useRouter, useSearchParams } from "next/navigation"

import { useLiveTurn } from "@/hooks/use-live-turn"
import { useCreateThread, useFlagMessage, useThread } from "@/hooks/use-threads"
import {
  deepLinkedSymbol,
  deepLinkedThread,
  openingState,
  readDeskSession,
  writeDeskSession,
} from "@/lib/alpha-desk/desk-session"
import { isActive, isSettled } from "@/lib/alpha-desk/live-turn"
import { buildTranscript, type OpenedAnalysis, type TranscriptEntry } from "@/lib/alpha-desk/transcript"
import type { FlagReason } from "@/lib/alpha-desk/types"

import { useShell } from "./shell-state"

/**
 * The conversation itself: the Thread, the Turn in flight, and sending.
 *
 * Lifted out of the surface that draws it, because in this shell three separate
 * regions need it — the sidebar lists the Threads and opens one, the top bar
 * names the current one, and the main column renders the transcript and the
 * composer. Passing it down would mean threading a dozen props through a layout
 * whose whole job is spatial.
 *
 * It owns exactly what the previous container owned:
 *
 * - **the Thread**, created lazily. A visit that asks nothing leaves no empty
 *   Thread behind, so the first question is what opens one;
 * - **the analysis context**, which is a workspace setting rather than a
 *   persistence key. It lives in the shell's state (one symbol selection, not
 *   two), and this reads it — switching it starts no Thread and ends none;
 * - **reattaching**, from what this tab remembered. A reload, a view change and
 *   a dropped network each end a subscriber; the Turn keeps running on the
 *   backend and is picked up wherever it got to (ADR-0013).
 */
interface DeskApi {
  threadId: string | null
  entries: TranscriptEntry[]
  /** A Turn is running, so the composer's control stops it rather than sending. */
  canCancel: boolean
  isCancelling: boolean
  isSubmitting: boolean
  /** An admission refusal, which is an HTTP outcome and never a stream event. */
  refusal: string | null
  flagFailedFor: number | null
  submit: (text: string) => void
  cancel: () => void
  retry: () => void
  flag: (messageId: number, reason: FlagReason) => void
  unflag: (messageId: number) => void
  dismissRefusal: () => void
  openThread: (id: string) => void
  newThread: () => void
  openAnalysis: (symbol: string, tradingDay: string) => void
}

const DeskContext = createContext<DeskApi | null>(null)

export function DeskProvider({ children }: { children: ReactNode }) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const symbolParam = searchParams.get("symbol")
  const threadParam = searchParams.get("thread")
  const { state: shell, dispatch: shellDispatch } = useShell()
  const activeSymbol = shell.contextSymbol

  // The deep link is on the URL, so the server render and the hydrating browser
  // read the same value and the first tree agrees. Read once: the effect below
  // strips `?symbol=` from the URL, and a live read would then see an arrival
  // that is no longer there.
  const [deepLinked] = useState(() => deepLinkedSymbol(symbolParam))
  // `?thread=` is *Open in new tab* from the sidebar menu, and is read and
  // consumed exactly like `?symbol=`: once, before the effect below strips it.
  const [deepLinkedThreadId] = useState(() => deepLinkedThread(threadParam))

  // What this tab remembered is *not* on the URL — `sessionStorage` exists only
  // in the browser, so seeding state from it during render makes the hydrated
  // tree disagree with the server HTML. It is applied after hydration instead.
  const [restored, setRestored] = useState(false)
  const [threadId, setThreadId] = useState<string | null>(null)
  // Sent, and the create has not committed it yet. Shown locally for exactly
  // that gap, then replaced by the copy the Thread comes back with.
  const [unconfirmedQuestion, setUnconfirmedQuestion] = useState<string | null>(null)
  // Held because there is no Thread to send it to yet.
  const [queuedQuestion, setQueuedQuestion] = useState<string | null>(null)
  // A Thread that could not be opened. Kept separately from the Turn's own
  // refusal because it is a different failure: nothing was admitted.
  const [threadError, setThreadError] = useState<string | null>(null)
  // The Analyses opened into the conversation on screen. Client state rather
  // than a persisted resource: an artifact is a thing the reader put in front
  // of themselves, not a message anybody sent.
  const [openedAnalyses, setOpenedAnalyses] = useState<OpenedAnalysis[]>([])

  const thread = useThread(threadId)
  const turn = useLiveTurn(threadId)
  const createThread = useCreateThread()
  const flagging = useFlagMessage(threadId)

  // The deep link is consumed once. Left in the URL, every later reload would
  // read as a fresh arrival and open yet another Thread.
  useEffect(() => {
    if (symbolParam !== null || threadParam !== null) {
      router.replace("/", { scroll: false })
    }
  }, [symbolParam, threadParam, router])

  const { attach } = turn
  useEffect(() => {
    if (restored) return
    setRestored(true)
    const opening = openingState(deepLinked, readDeskSession(), deepLinkedThreadId)
    setThreadId(opening.threadId)
    if (opening.activeSymbol !== null) {
      shellDispatch({ type: "context-symbol", symbol: opening.activeSymbol })
    }
    // Only for the deep link. A remembered Thread must not drag a reader who
    // left the tab on the board back into the conversation.
    if (deepLinkedThreadId !== null) shellDispatch({ type: "view", view: "chat" })
    if (opening.turnId && opening.threadId) attach(opening.turnId, opening.threadId)
  }, [restored, deepLinked, deepLinkedThreadId, attach, shellDispatch])

  // What this tab was doing, for the next mount. A settled Turn is forgotten:
  // reattaching to it would open a stream for a Turn the transcript already
  // shows as a canonical message.
  const liveTurnId = turn.state.turnId
  const turnSettled = isSettled(turn.state)
  useEffect(() => {
    if (!restored) return
    writeDeskSession({
      threadId,
      turnId: turnSettled ? null : liveTurnId,
      activeSymbol,
    })
  }, [restored, threadId, liveTurnId, turnSettled, activeSymbol])

  // -- sending ------------------------------------------------------------

  const { send } = turn
  const submit = useCallback(
    (text: string) => {
      setUnconfirmedQuestion(text)
      setThreadError(null)
      if (threadId) {
        // `symbols` stays empty and the context travels as `active_symbol`.
        // They are different things, and guessing which symbols a sentence is
        // *about* would put a parser in the browser and a wrong answer in the
        // idempotency payload.
        void send({ text, activeSymbol })
        return
      }
      setQueuedQuestion(text)
      createThread.mutate(undefined, {
        onSuccess: (created) => setThreadId(created.id),
        onError: (error) => {
          // Nothing stays queued behind a Thread that does not exist.
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
        openedAnalyses,
      }),
    [threadId, messages, turn.state, unconfirmedQuestion, openedAnalyses],
  )

  // Read through a ref so opening an Analysis does not re-create the callback
  // on every message that lands.
  const messagesRef = useRef(messages)
  messagesRef.current = messages

  const openAnalysis = useCallback((symbol: string, tradingDay: string) => {
    setOpenedAnalyses((opened) => {
      if (opened.some((one) => one.symbol === symbol && one.tradingDay === tradingDay)) {
        return opened
      }
      const afterSeq = messagesRef.current.reduce(
        (highest, message) => Math.max(highest, message.seq),
        0,
      )
      return [...opened, { symbol, tradingDay, afterSeq }]
    })
  }, [])

  const lastQuestion = useMemo(() => {
    for (let index = entries.length - 1; index >= 0; index -= 1) {
      const entry = entries[index]
      if (entry.kind === "user") return entry.text
    }
    return null
  }, [entries])

  const { retry: retryTurn } = turn
  const retry = useCallback(() => {
    // A new Turn pointing at the old one. The previous Turn and everything it
    // wrote stay exactly where they are.
    if (lastQuestion === null) return
    setUnconfirmedQuestion(null)
    void retryTurn({ text: lastQuestion, activeSymbol })
  }, [lastQuestion, activeSymbol, retryTurn])

  // -- the one dispute action ---------------------------------------------

  const { flag, unflag } = flagging
  const onFlag = useCallback(
    (messageId: number, reason: FlagReason) => flag.mutate({ messageId, reason }),
    [flag],
  )
  const onUnflag = useCallback((messageId: number) => unflag.mutate(messageId), [unflag])

  // Both of these leave the conversation the artifacts were opened into, so
  // they leave with it.
  const openThread = useCallback((id: string) => {
    setThreadId(id)
    setUnconfirmedQuestion(null)
    setThreadError(null)
    setOpenedAnalyses([])
  }, [])

  const { clearRefusal, reset } = turn
  const newThread = useCallback(() => {
    setThreadId(null)
    setUnconfirmedQuestion(null)
    setThreadError(null)
    setOpenedAnalyses([])
    reset()
  }, [reset])

  const dismissRefusal = useCallback(() => {
    setThreadError(null)
    clearRefusal()
  }, [clearRefusal])

  const value = useMemo<DeskApi>(
    () => ({
      threadId,
      entries,
      canCancel: isActive(turn.state),
      isCancelling: turn.state.phase === "cancelling",
      isSubmitting: createThread.isPending || queuedQuestion !== null,
      refusal: turn.refusal?.message ?? threadError,
      flagFailedFor: flagging.failedMessageId,
      submit,
      cancel: turn.cancel,
      retry,
      flag: onFlag,
      unflag: onUnflag,
      dismissRefusal,
      openThread,
      newThread,
      openAnalysis,
    }),
    [
      threadId,
      entries,
      turn.state,
      turn.refusal,
      turn.cancel,
      createThread.isPending,
      queuedQuestion,
      threadError,
      flagging.failedMessageId,
      submit,
      retry,
      onFlag,
      onUnflag,
      dismissRefusal,
      openThread,
      newThread,
      openAnalysis,
    ],
  )

  return <DeskContext.Provider value={value}>{children}</DeskContext.Provider>
}

export function useDesk(): DeskApi {
  const value = useContext(DeskContext)
  if (value === null) throw new Error("useDesk must be used inside <DeskProvider>")
  return value
}
