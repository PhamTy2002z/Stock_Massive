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

import { buildingLabel } from "@/components/signal-desk/signal-desk-building"
import { useAnswerReveal } from "@/hooks/use-answer-reveal"
import { useLiveTurn } from "@/hooks/use-live-turn"
import {
  useCreateThread,
  useFlagMessage,
  useHelpfulMessage,
  useThread,
} from "@/hooks/use-threads"
import {
  deepLinkedSymbol,
  deepLinkedThread,
  openingState,
  readDeskSession,
  rememberSignalDesk,
  signalDeskOn,
  writeDeskSession,
} from "@/lib/alpha-desk/desk-session"
import { readPreferences } from "@/lib/alpha-desk/preferences"
import { isActive, isSettled, resendPlan } from "@/lib/alpha-desk/live-turn"
import {
  buildTranscript,
  storedDeskViews,
  type OpenedAnalysis,
  type TranscriptEntry,
} from "@/lib/alpha-desk/transcript"
import type { FlagReason } from "@/lib/alpha-desk/types"
import { describeFailure, type Failure } from "@/lib/failure"

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
  /**
   * The same refusal, classified — so the banner can offer a way out of it.
   *
   * Beside `refusal` rather than replacing it: the message is what the backend
   * wrote about *this* request and is often more specific than any category
   * ("ngân sách lượt đã hết"), while the classification is what knows that a
   * 401 means the reader should sign in again. The banner shows the first and
   * takes its recovery from the second.
   */
  refusalFailure: Failure | null
  /**
   * Whether the Signal Desk is on for the conversation on screen.
   *
   * Read from the shell, which owns the layout the switch changes, and exposed
   * here because the composer's pill is the one control that sets it. One edge
   * in and one edge out: an entitlement check, when there is one, goes on
   * `setSignalDesk` and nowhere else.
   */
  signalDesk: boolean
  /**
   * Turn the desk on or off for this conversation.
   *
   * The single function the flag passes through. Today it changes the layout;
   * when the transport carries a mode, this is where the request payload learns
   * about it, rather than every surface that can toggle the switch.
   */
  setSignalDesk: (on: boolean) => void
  /**
   * What a Study in flight should be called, or null when none is.
   *
   * One derivation, two readers: the pill in the composer is this state's
   * status light and the pane's skeleton is its shape. Computing it twice is
   * how the two end up disagreeing about whether anything is happening.
   */
  building: string | null
  flagFailedFor: number | null
  submit: (text: string) => void
  cancel: () => void
  retry: () => void
  /** Ask one of the questions already in the transcript again. */
  resend: (text: string) => void
  flag: (messageId: number, reason: FlagReason) => void
  unflag: (messageId: number) => void
  /** Leave the positive verdict on one answer, or take it back. */
  helpful: (messageId: number, helpful: boolean) => void
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
  const [threadError, setThreadError] = useState<Error | null>(null)
  // The Analyses opened into the conversation on screen. Client state rather
  // than a persisted resource: an artifact is a thing the reader put in front
  // of themselves, not a message anybody sent.
  const [openedAnalyses, setOpenedAnalyses] = useState<OpenedAnalysis[]>([])
  // Which conversations this tab has the desk switched on for. Held here rather
  // than in the shell because it outlives the conversation on screen: the shell
  // knows whether *this* desk is open, and this knows which Thread to restore
  // that answer for.
  const [signalDeskThreads, setSignalDeskThreads] = useState<string[]>([])

  const thread = useThread(threadId)
  const turn = useLiveTurn(threadId)
  const createThread = useCreateThread()
  const flagging = useFlagMessage(threadId)
  const helpfulness = useHelpfulMessage(threadId)

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
    const session = readDeskSession()
    const opening = openingState(deepLinked, session, deepLinkedThreadId)
    setThreadId(opening.threadId)
    setSignalDeskThreads(session.signalDeskThreads ?? [])
    // The desk the arriving Thread was left with — or, where there is no
    // Thread to arrive at, what this browser says a new conversation opens
    // with. A deep link lands in the second case: it opens a conversation that
    // has no answer yet, and so has no mode of its own to restore.
    shellDispatch({
      type: "thread",
      signalDesk:
        opening.threadId === null
          ? readPreferences().signalDeskByDefault
          : signalDeskOn(session, opening.threadId),
      opened: false,
    })
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
      signalDeskThreads,
    })
  }, [restored, threadId, liveTurnId, turnSettled, activeSymbol, signalDeskThreads])

  // The switch, recorded against the Thread it was thrown for. Watched rather
  // than written in the handler because the desk can be switched on before
  // there is a Thread to attach it to: the first question opens one, and this
  // is what files the answer under it when it arrives.
  const signalDesk = shell.signalDesk
  useEffect(() => {
    if (!restored || threadId === null) return
    setSignalDeskThreads((threads) => rememberSignalDesk(threads, threadId, signalDesk))
  }, [restored, threadId, signalDesk])

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
          // Kept as the thrown value rather than as its message: the status on
          // it is what tells the banner whether to offer a retry or a sign-in.
          setThreadError(
            error instanceof Error ? error : new Error("Không mở được cuộc trò chuyện."),
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

  // The pictures this conversation already made, put back in the strip.
  //
  // Runs off the stored messages rather than off the live Turn: the Turn that
  // drew them ended in another session, possibly on another day. Without this
  // the strip stayed empty until a *new* Study ran, so an old Thread's desk
  // views existed, were fetchable, and were reachable only by scrolling the
  // transcript back to the card that opened them.
  const storedTabs = useMemo(
    () =>
      storedDeskViews(messages).map((deskView) => ({
        artifactId: deskView.artifactId,
        title: deskView.title,
      })),
    [messages],
  )
  useEffect(() => {
    if (storedTabs.length === 0) return
    shellDispatch({ type: "desk-views-restored", tabs: storedTabs })
  }, [storedTabs, shellDispatch])

  // A desk view the Turn produced opens the panel on it — once, and only while the
  // reader has not pinned another tab themselves. Keyed on the newest
  // announcement rather than the list, so re-renders of an unchanged Turn do
  // not keep re-opening a panel the reader has closed.
  const newestDeskView = turn.state.deskViews[turn.state.deskViews.length - 1]
  const newestDeskViewId = newestDeskView?.artifactId ?? null
  useEffect(() => {
    if (newestDeskViewId === null) return
    shellDispatch({ type: "signal-desk-ready", artifactId: newestDeskViewId })
  }, [newestDeskViewId, shellDispatch])

  // -- what is on screen --------------------------------------------------

  // How much of the answer is on screen. Held here rather than in the view for
  // two reasons that are one: every step of it has to be a commit of the
  // transcript, which is what the pin and the spacer are built on, and it has to
  // survive the reader switching views mid-answer.
  const reveal = useAnswerReveal(turn.state)

  const entries = useMemo(
    () =>
      buildTranscript({
        threadId,
        messages,
        live: turn.state,
        pendingUserText: unconfirmedQuestion,
        openedAnalyses,
        reveal,
      }),
    [threadId, messages, turn.state, unconfirmedQuestion, openedAnalyses, reveal],
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

  /**
   * Ask a question from the transcript again, from the message that carries it.
   *
   * Two different things wear the same label. Asking the *last* question again
   * after its Turn ended badly is a retry, and goes out with
   * `retry_of_turn_id` set so the two Turns are linked — that is what a Turn
   * that hung, failed or was cancelled needs. Asking any *earlier* question
   * again is a new question that happens to repeat one, and must not claim to
   * be a second attempt at a Turn that already answered.
   *
   * Nothing is sent while a Turn is in flight. The composer offers Stop rather
   * than Send for exactly that stretch, and a resend that slipped past it would
   * open a second Turn behind the one on screen.
   */
  const resend = useCallback(
    (text: string) => {
      const plan = resendPlan(turn.state, text === lastQuestion)
      if (plan === "retry") retry()
      else if (plan === "submit") submit(text)
    },
    [turn.state, lastQuestion, retry, submit],
  )

  // -- the two verdicts ---------------------------------------------------

  const { flag, unflag } = flagging
  const onFlag = useCallback(
    (messageId: number, reason: FlagReason) => flag.mutate({ messageId, reason }),
    [flag],
  )
  const onUnflag = useCallback((messageId: number) => unflag.mutate(messageId), [unflag])

  // One callback for both directions, because the caller knows which state the
  // press is asking for and the two endpoints differ only in method.
  const { mark, unmark } = helpfulness
  const onHelpful = useCallback(
    (messageId: number, helpful: boolean) =>
      helpful ? mark.mutate(messageId) : unmark.mutate(messageId),
    [mark, unmark],
  )

  // Both of these leave the conversation the artifacts were opened into, so
  // they leave with it.
  // Read through a ref so the two below do not re-create themselves every time
  // a desk is switched somewhere.
  const deskThreadsRef = useRef(signalDeskThreads)
  deskThreadsRef.current = signalDeskThreads

  const openThread = useCallback(
    (id: string) => {
      setThreadId(id)
      setUnconfirmedQuestion(null)
      setThreadError(null)
      setOpenedAnalyses([])
      // Re-read rather than carry forward: the desk belongs to the conversation
      // being opened, and the one being left keeps its own answer.
      shellDispatch({
        type: "thread",
        signalDesk: deskThreadsRef.current.includes(id),
        opened: true,
      })
    },
    [shellDispatch],
  )

  const { clearRefusal, reset } = turn
  const newThread = useCallback(() => {
    setThreadId(null)
    setUnconfirmedQuestion(null)
    setThreadError(null)
    setOpenedAnalyses([])
    // A new conversation starts where this browser says new conversations
    // start, whatever the last one did. The preference answers only this
    // question: a Thread with history restores its own mode instead.
    shellDispatch({
      type: "thread",
      signalDesk: readPreferences().signalDeskByDefault,
      opened: true,
    })
    reset()
  }, [reset, shellDispatch])

  const setSignalDesk = useCallback(
    (on: boolean) => shellDispatch({ type: "signal-desk", on }),
    [shellDispatch],
  )

  const dismissRefusal = useCallback(() => {
    setThreadError(null)
    clearRefusal()
  }, [clearRefusal])

  // One value behind both fields, so the sentence and the way out of it can
  // never come from two different failures.
  const refusalError: Error | null = turn.refusal ?? threadError

  const value = useMemo<DeskApi>(
    () => ({
      threadId,
      entries,
      canCancel: isActive(turn.state),
      isCancelling: turn.state.phase === "cancelling",
      isSubmitting: createThread.isPending || queuedQuestion !== null,
      refusal: refusalError?.message ?? null,
      refusalFailure: refusalError === null ? null : describeFailure(refusalError),
      signalDesk,
      setSignalDesk,
      building: buildingLabel(turn.state),
      flagFailedFor: flagging.failedMessageId,
      submit,
      cancel: turn.cancel,
      retry,
      resend,
      flag: onFlag,
      unflag: onUnflag,
      helpful: onHelpful,
      dismissRefusal,
      openThread,
      newThread,
      openAnalysis,
    }),
    [
      threadId,
      entries,
      turn.state,
      refusalError,
      turn.cancel,
      createThread.isPending,
      queuedQuestion,
      flagging.failedMessageId,
      signalDesk,
      setSignalDesk,
      submit,
      retry,
      resend,
      onFlag,
      onUnflag,
      onHelpful,
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
