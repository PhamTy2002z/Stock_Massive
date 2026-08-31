"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { useRouter, useSearchParams } from "next/navigation"

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
  writeDeskSession,
} from "@/lib/alpha-desk/desk-session"
import { isActive, isSettled, resendPlan } from "@/lib/alpha-desk/live-turn"
import {
  buildTranscript,
  questionBefore,
  type TranscriptEntry,
} from "@/lib/alpha-desk/transcript"
import { uploadAttachment } from "@/lib/alpha-desk/api"
import { attachmentRefusal } from "@/lib/alpha-desk/copy"
import { canCapture, captureScreen } from "@/lib/alpha-desk/screen-capture"
import { AlphaRefusalError } from "@/lib/alpha"
import { useCapabilities } from "@/hooks/use-capabilities"
import type { Attachment, FlagReason } from "@/lib/alpha-desk/types"
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
/**
 * One attachment on a question that has not been sent yet.
 *
 * Keyed locally rather than by the server's id, because a chip has to be on
 * screen — named, sized, showing its thumbnail — while the upload is still in
 * flight and no id exists. `id` arrives when the upload lands, and it is the
 * only field the Turn request carries.
 */
export interface PendingAttachment {
  /** Stable for the life of the chip, from before the upload to after it. */
  key: string
  filename: string
  byteSize: number
  mediaType: string
  image: boolean
  /** A local `blob:` URL for an image, so the reader sees it before it uploads. */
  previewUrl?: string
  /** The server's id. Null while uploading, and null forever if it failed. */
  id: string | null
  status: "uploading" | "ready" | "error"
  /** Why it failed, already in the product's own words. */
  error?: string
}

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
  flagFailedFor: number | null
  submit: (text: string) => void
  /** What this unsent question carries, in the order it was added. */
  attachments: PendingAttachment[]
  /** Take files from a picker, a shortcut, or a capture, and start uploading. */
  attach: (files: File[]) => void
  /** Take one chip back off the question. */
  detach: (key: string) => void
  /**
   * The frame just captured, waiting to be looked at, or null.
   *
   * Held here rather than in the shell because it is part of the question being
   * written: accepting it makes it an attachment like any other.
   */
  capture: { previewUrl: string } | null
  /** Ask the browser for a window or a screen. Opens the preview on success. */
  startCapture: () => void
  /** Attach the frame that was captured. */
  acceptCapture: () => void
  /** Throw it away, leaving nothing behind. */
  discardCapture: () => void
  /** Whether this browser can capture at all. Drawn as a disabled row when not. */
  captureSupported: boolean
  /**
   * Whether the configured route reads images.
   *
   * `true` until the answer arrives, so the note about pictures not being read
   * does not flash on every load of a deployment where they are.
   */
  visionEnabled: boolean
  cancel: () => void
  retry: () => void
  /** Ask one of the questions already in the transcript again. */
  /**
   * Ask a question from the transcript again, with what it carried.
   *
   * The attachments are a parameter because the caller is the message that
   * holds them: an earlier question asked again is a new question, and its
   * files are the ones stored against *that* message.
   */
  resend: (text: string, attachments?: string[]) => void
  flag: (messageId: number, reason: FlagReason) => void
  unflag: (messageId: number) => void
  /** Leave the positive verdict on one answer, or take it back. */
  helpful: (messageId: number, helpful: boolean) => void
  dismissRefusal: () => void
  openThread: (id: string) => void
  newThread: () => void
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
  // The ids the queued question carries. Held beside it rather than re-read
  // from the pending list when the Thread arrives: by then a second file may
  // have finished uploading, and a question must go out with what it was sent
  // with rather than with whatever had landed by the time a Thread existed.
  const [queuedAttachments, setQueuedAttachments] = useState<string[]>([])
  // What the unsent question carries. Beside `queuedQuestion` because it
  // belongs to the same thing: a question nobody has sent yet.
  const [pending, setPending] = useState<PendingAttachment[]>([])

  /**
   * The ids a question is allowed to carry: the ones that finished uploading.
   *
   * A chip still in flight or failed is not in the list. Sending its key would
   * be sending an id that does not exist, which the backend answers 404 — the
   * reader's whole question refused over one file.
   */
  const readyIds = useMemo(
    () => pending.filter((entry) => entry.id !== null).map((entry) => entry.id as string),
    [pending],
  )

  // A Thread that could not be opened. Kept separately from the Turn's own
  // refusal because it is a different failure: nothing was admitted.
  const [threadError, setThreadError] = useState<Error | null>(null)

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
    // The desk the arriving Thread was left with — or, where there is no
    // Thread to arrive at, what this browser says a new conversation opens
    // with. A deep link lands in the second case: it opens a conversation that
    // has no answer yet, and so has no mode of its own to restore.
    shellDispatch({ type: "thread", opened: false })
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
      // Written because the rows already exist server-side. A reload that
      // forgot them would leave files in the database that nothing on screen
      // refers to, filling the reader's own quota with invisible uploads until
      // the orphan sweep.
      pendingAttachments: readyIds,
    })
  }, [
    restored,
    threadId,
    liveTurnId,
    turnSettled,
    activeSymbol,
    readyIds,
  ])

  // -- attaching ----------------------------------------------------------

  const capabilities = useCapabilities()

  /**
   * Upload each file now, and show it now.
   *
   * The chip appears before the request finishes, with the local thumbnail
   * already drawn, because the reader is still typing and the whole value of
   * uploading early is that they are not made to wait at Send.
   *
   * Every failure becomes a sentence on the chip rather than a thrown error:
   * one file that would not upload must not stop the question, and must not
   * empty the field the reader has been writing in.
   */
  const attachFiles = useCallback((files: File[]) => {
    if (files.length === 0) return
    for (const file of files) {
      const key = `${file.name}-${file.size}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      const image = file.type.startsWith("image/")
      const previewUrl = image ? URL.createObjectURL(file) : undefined
      setPending((current) => [
        ...current,
        {
          key,
          filename: file.name,
          byteSize: file.size,
          mediaType: file.type,
          image,
          previewUrl,
          id: null,
          status: "uploading",
        },
      ])
      void uploadAttachment(file)
        .then((stored) =>
          setPending((current) =>
            current.map((entry) =>
              entry.key === key
                ? { ...entry, id: stored.id, byteSize: stored.byte_size, status: "ready" }
                : entry,
            ),
          ),
        )
        .catch((cause: unknown) =>
          setPending((current) =>
            current.map((entry) =>
              entry.key === key
                ? {
                    ...entry,
                    status: "error",
                    error: attachmentRefusal(
                      cause instanceof AlphaRefusalError ? cause.reason : null,
                    ),
                  }
                : entry,
            ),
          ),
        )
    }
  }, [])

  // The captured frame and its preview URL, together, so neither can be
  // released without the other.
  const [capture, setCapture] = useState<{ file: File; previewUrl: string } | null>(null)

  const detach = useCallback((key: string) => {
    setPending((current) => {
      const going = current.find((entry) => entry.key === key)
      // Released here rather than in an effect keyed on the list: this is the
      // moment the URL stops being needed, and an effect would have to diff two
      // arrays to work out which one to revoke.
      if (going?.previewUrl) URL.revokeObjectURL(going.previewUrl)
      return current.filter((entry) => entry.key !== key)
    })
  }, [])

  /**
   * Ask for a frame, then show it. Never send it.
   *
   * The overlay opens only on success. A reader who dismissed the browser's own
   * picker gets nothing at all — that is a change of mind, not a failure, and an
   * error message over it would be the interface arguing with them.
   */
  const startCapture = useCallback(() => {
    void captureScreen().then((file) => {
      if (file === null) return
      setCapture({ file, previewUrl: URL.createObjectURL(file) })
      shellDispatch({ type: "overlay", overlay: "capture" })
    })
  }, [shellDispatch])

  const closeCapture = useCallback(() => {
    setCapture((current) => {
      if (current) URL.revokeObjectURL(current.previewUrl)
      return null
    })
    shellDispatch({ type: "overlay", overlay: null })
  }, [shellDispatch])

  const acceptCapture = useCallback(() => {
    // Down the same pipe as a chosen file, because that is all it is now: one
    // more image on this question, with the same ceilings and the same chip.
    if (capture) attachFiles([capture.file])
    closeCapture()
  }, [capture, attachFiles, closeCapture])

  const clearPending = useCallback(() => {
    setPending((current) => {
      for (const entry of current) {
        if (entry.previewUrl) URL.revokeObjectURL(entry.previewUrl)
      }
      return []
    })
  }, [])

  /** The chips a sent-but-uncommitted question shows, from what was pending. */
  const pendingAttachmentViews = useMemo<Attachment[]>(
    () =>
      pending
        .filter((entry) => entry.id !== null)
        .map((entry) => ({
          id: entry.id as string,
          filename: entry.filename,
          media_type: entry.mediaType,
          byte_size: entry.byteSize,
        })),
    [pending],
  )

  // -- sending ------------------------------------------------------------

  const { send } = turn

  /**
   * Send one question with one explicit list of attachments.
   *
   * The list is a parameter rather than read from state, because the four
   * places that send a question do not agree about where it comes from: the
   * composer sends what is pending, the queued effect sends what was pending
   * when the reader pressed Send, a retry sends what the last question carried,
   * and a resend sends what *that* message carried. A single reader of state
   * here would have been right for one of the four.
   */
  const submitWith = useCallback(
    (text: string, attachments: string[]) => {
      setUnconfirmedQuestion(text)
      setThreadError(null)
      if (threadId) {
        // `symbols` stays empty: guessing which symbols a sentence is *about*
        // would put a parser in the browser and a wrong answer in the
        // idempotency payload. The analysis lens is not sent either — it has no
        // reader on the other side, and a field nothing declares is dropped in
        // silence, which reads from here as a lens that travels when it does
        // not. It changes this composer and stops there until something behind
        // the request is designed to receive it.
        void send({ text, attachments })
        return
      }
      setQueuedQuestion(text)
      setQueuedAttachments(attachments)
      createThread.mutate(undefined, {
        onSuccess: (created) => setThreadId(created.id),
        onError: (error) => {
          // Nothing stays queued behind a Thread that does not exist. The
          // attachments are *not* dropped: the rows are still there and the
          // chips are still on screen, so a second press sends the same files
          // rather than making the reader choose them again.
          setQueuedQuestion(null)
          setQueuedAttachments([])
          setUnconfirmedQuestion(null)
          // Kept as the thrown value rather than as its message: the status on
          // it is what tells the banner whether to offer a retry or a sign-in.
          setThreadError(
            error instanceof Error ? error : new Error("Không mở được cuộc trò chuyện."),
          )
        },
      })
    },
    [threadId, send, createThread],
  )

  /** What the composer calls: this question, carrying what is pending. */
  const submit = useCallback(
    (text: string) => {
      submitWith(text, readyIds)
      clearPending()
    },
    [submitWith, readyIds, clearPending],
  )

  // The first question of a Thread goes out here, after the create returns.
  // The attachment rows carry no `thread_id` precisely so their ids survive
  // this gap — the upload happened before there was a Thread to belong to.
  useEffect(() => {
    if (!threadId || queuedQuestion === null) return
    const text = queuedQuestion
    setQueuedQuestion(null)
    const attachments = queuedAttachments
    setQueuedAttachments([])
    void send({ text, attachments })
  }, [threadId, queuedQuestion, queuedAttachments, send])

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
        pendingAttachments: pendingAttachmentViews,
        reveal,
      }),
    [
      threadId,
      messages,
      turn.state,
      unconfirmedQuestion,
      pendingAttachmentViews,
      reveal,
    ],
  )

  // The last question asked, with what it carried. From `questionBefore` rather
  // than derived here, because the transcript's own module is where that
  // decision lives and the resend control in `view-chat` asks it the same way.
  const lastQuestion = useMemo(() => questionBefore(entries), [entries])

  const { retry: retryTurn } = turn
  const retry = useCallback(() => {
    // A new Turn pointing at the old one. The previous Turn and everything it
    // wrote stay exactly where they are.
    if (lastQuestion === null) return
    setUnconfirmedQuestion(null)
    void retryTurn({
      text: lastQuestion.text,
      attachments: lastQuestion.attachments,
    })
  }, [lastQuestion, retryTurn])

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
    (text: string, attachments: string[] = []) => {
      const plan = resendPlan(turn.state, text === lastQuestion?.text)
      if (plan === "retry") retry()
      // The fourth call site, and the one the first draft of this plan did not
      // count. An earlier question asked again is a *new* question, so its
      // attachments come from the message that carries them rather than from
      // `lastQuestion` — that one is a different question entirely.
      else if (plan === "submit") submitWith(text, attachments)
    },
    [turn.state, lastQuestion, retry, submitWith],
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

  const openThread = useCallback(
    (id: string) => {
      setThreadId(id)
      setUnconfirmedQuestion(null)
      setThreadError(null)
      shellDispatch({ type: "thread", opened: true })
    },
    [shellDispatch],
  )

  const { clearRefusal, reset } = turn
  const newThread = useCallback(() => {
    setThreadId(null)
    setUnconfirmedQuestion(null)
    setThreadError(null)
    shellDispatch({ type: "thread", opened: true })
    reset()
  }, [reset, shellDispatch])

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
      attachments: pending,
      attach: attachFiles,
      detach,
      capture: capture === null ? null : { previewUrl: capture.previewUrl },
      startCapture,
      acceptCapture,
      discardCapture: closeCapture,
      captureSupported: canCapture(),
      visionEnabled: capabilities.vision,
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
      pending,
      attachFiles,
      detach,
      capture,
      startCapture,
      acceptCapture,
      closeCapture,
      capabilities.vision,
      submit,
      retry,
      resend,
      onFlag,
      onUnflag,
      onHelpful,
      dismissRefusal,
      openThread,
      newThread,
    ],
  )

  return <DeskContext.Provider value={value}>{children}</DeskContext.Provider>
}

export function useDesk(): DeskApi {
  const value = useContext(DeskContext)
  if (value === null) throw new Error("useDesk must be used inside <DeskProvider>")
  return value
}
