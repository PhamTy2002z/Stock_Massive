"use client"

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react"
import { AlertCircle, Check, Copy, Pencil, RotateCcw, X } from "lucide-react"

import { AssistantMessage } from "@/components/alpha/message/assistant-message"
import { AttachmentChip } from "@/components/shell/attachment-chip"
import { DraftMessage } from "@/components/alpha/message/draft-message"
import { VisgniteMark } from "@/components/shared/visgnite-logo"
import { useAuth } from "@/hooks/use-auth"
import { attachmentUrl } from "@/lib/alpha-desk/api"
import { pinStep } from "@/lib/alpha-desk/pin-question"
import { questionBefore } from "@/lib/alpha-desk/transcript"
import { isImageAttachment, type Attachment } from "@/lib/alpha-desk/types"
import { greetingFor, plainGreeting } from "@/lib/greeting"
import { vietnamPartOfDay } from "@/lib/market-session"
import Link from "next/link"
import { cn } from "@/lib/utils"

import { Composer } from "./composer"
import { useDesk } from "./desk-state"
import { IconButton } from "./primitives"
import { useShell } from "./shell-state"

/**
 * Put one answer on the clipboard, and say nothing when the browser refuses.
 *
 * A browser can refuse — no permission, an insecure origin — and that is not
 * worth an error over text the reader can still select by hand. The button's
 * own "Đã chép" is optimistic for the same reason the question bubble's is.
 */
function copyText(text: string): void {
  void navigator.clipboard?.writeText(text).catch(() => {})
}

/**
 * The question this answer answers, or nothing.
 *
 * Read backwards from the answer rather than carried on it, because the pairing
 * is a fact about the transcript's order and the message does not record which
 * question produced it. Nothing happens when there is no question above — an
 * answer with nothing before it is not something to re-ask.
 */
/** How close to the bottom still counts as "following" the newest content. */
const FOLLOW_THRESHOLD_PX = 120

/** Breathing room left above a question pinned to the top of the viewport. */
const ANCHOR_PAD_PX = 14

/**
 * A layout effect in the browser, an ordinary one on the server.
 *
 * The pin has to be applied *before the browser paints*, or the reader sees the
 * transcript at its old position for a frame and then jump. `useLayoutEffect` is
 * the only hook that promises that, and it warns when React renders this tree on
 * the server — where there is no layout to read and nothing to scroll.
 */
const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect

/**
 * The conversation: a transcript that scrolls, and a composer docked over it.
 *
 * **The transcript scrolls, not the page.** The shell is pinned to one viewport
 * so the sidebar and the composer stay where the user left them; if this
 * element did not own its overflow, a long answer would push the composer off
 * the bottom of the screen.
 *
 * The composer floats *over* the transcript rather than sitting under it, and
 * the scroll container reserves the height it occupies. That is what lets the
 * last answer stay visually continuous with the field asking the next question,
 * which a bordered footer would cut in half.
 *
 * **A follow-up question goes to the top of the viewport, not to the bottom.**
 * The answer being read scrolls out above it and the new one has the whole
 * screen to arrive into, which is what makes a long conversation legible: the
 * reader's eye stays at one height instead of chasing the last line down the
 * page. Pinning a question needs room underneath it that does not exist yet, so
 * the transcript ends in a spacer sized to exactly the shortfall — and the
 * spacer melts away as the answer grows into it, which is why nothing moves
 * while the answer streams. Once the answer is taller than the screen there is
 * no shortfall left, the spacer is gone, and following the bottom takes over
 * again.
 */
/**
 * The mark, and the time of day, on Vietnam's clock.
 *
 * Kept here rather than in its own file: the greeting is only ever shown by
 * this view's empty state, and pulling it out would cost an import without
 * saving anything. Random line per mount is drawn once and gated on the auth
 * query settling — until then the safe `plainGreeting` renders on both sides
 * so hydration stays quiet.
 */
function Greeting() {
  const { user, isPending } = useAuth()
  const [roll] = useState(Math.random)
  const name = user?.full_name?.trim() || user?.email?.split("@")[0] || null
  const partOfDay = vietnamPartOfDay()
  const line = isPending
    ? plainGreeting(partOfDay, name)
    : greetingFor(partOfDay, name, roll)

  return (
    <div className="flex items-center justify-center gap-3">
      <VisgniteMark className="h-[26px] w-[17px]" />
      <h2 className="min-w-0 font-serif text-[clamp(1.6rem,2.7vw,2.15rem)] font-normal leading-[1.1] tracking-[-0.01em] text-ink-display">
        {line}
      </h2>
    </div>
  )
}

export function ChatView() {
  const desk = useDesk()
  const { dispatch } = useShell()
  const container = useRef<HTMLDivElement>(null)
  const following = useRef(true)
  const pinned = useRef(false)
  const landing = useRef(false)
  const anchor = useRef<HTMLDivElement | null>(null)
  const [tail, setTail] = useState(0)
  const tailHeight = useRef(0)

  // What identifies "the reader asked something". Counted rather than keyed off
  // the entry itself: a pending question and the committed one that replaces it
  // are two keys for one question, and re-anchoring on the swap would jump the
  // page a second time for nothing.
  const questionCount = desk.entries.reduce(
    (total, entry) => (entry.kind === "user" ? total + 1 : total),
    0,
  )
  const asked = useRef(questionCount)
  const thread = useRef(desk.threadId)
  const lastQuestionIndex = desk.entries.reduce(
    (found, entry, index) => (entry.kind === "user" ? index : found),
    -1,
  )

  /** Where the pinned question would sit, as an offset into the transcript. */
  const anchorOffset = useCallback(() => {
    const element = container.current
    const question = anchor.current
    if (!element || !question) return null
    // Measured against the viewport rather than read from `offsetTop`: the
    // scroll container is not the offset parent here, and which ancestor is
    // positioned is a layout detail this must not depend on.
    const top = question.getBoundingClientRect().top - element.getBoundingClientRect().top
    return top + element.scrollTop - ANCHOR_PAD_PX
  }, [])

  /**
   * What the pin needs from the layout right now: the spacer it wants, and
   * whether the room for the scroll is already there.
   *
   * The arithmetic lives in `pin-question.ts`, where it has tests. Twice it was
   * wrong in here, in ways the view could not show — that file says how.
   */
  const step = useCallback((): { tail: number; scroll: number | null } => {
    const element = container.current
    const target = anchorOffset()
    if (!element || target === null) return { tail: 0, scroll: null }
    return pinStep({
      target,
      scrollHeight: element.scrollHeight,
      clientHeight: element.clientHeight,
      tail: tailHeight.current,
    })
  }, [anchorOffset])

  const setTailHeight = useCallback((next: number) => {
    if (next === tailHeight.current) return
    tailHeight.current = next
    setTail(next)
  }, [])

  // A new question, or a different Thread. Before the browser paints, so a
  // question never appears at the bottom for a frame on its way to the top.
  useIsoLayoutEffect(() => {
    const element = container.current
    if (!element) return

    const switched = thread.current !== desk.threadId
    thread.current = desk.threadId
    const isNew = questionCount > asked.current
    asked.current = questionCount

    if (switched) {
      // Reopening a Thread lands at its end. The last answer is what the reader
      // came back for, not the question that produced it.
      pinned.current = false
      landing.current = false
      following.current = true
      setTailHeight(0)
      element.scrollTop = element.scrollHeight
      return
    }

    if (!isNew) return

    pinned.current = true
    following.current = true
    // Only the intention. The spacer and the scroll are the effect below, which
    // is the one place that knows whether the layout can carry them yet.
    landing.current = true
  }, [questionCount, desk.threadId, setTailHeight])

  /**
   * Putting the new question at the top, on whichever commit the layout can.
   *
   * Two steps, and the order between them is the whole point. The top of the
   * viewport is only a scroll position the transcript *has* if the transcript is
   * tall enough, so the spacer has to exist in the DOM before the scroll is
   * asked for. Asking for both in one frame is what made the pin land sometimes
   * and stop halfway other times — the frame either won the race with React's
   * commit or it did not, and a heavier answer above made it lose.
   *
   * When the room is there, `pinStep` hands back the position to scroll to;
   * until then it hands back the spacer to make and nothing to scroll.
   *
   * Runs after every commit and leaves on its first line unless a pin is
   * waiting, which is why it has no dependency list: every way the transcript
   * can change height is a commit, and naming them would be naming them twice.
   */
  useIsoLayoutEffect(() => {
    if (!landing.current) return
    const element = container.current
    if (!element) return

    const plan = step()
    if (plan.scroll === null) {
      // The room is not in the DOM yet. Put it there and finish on the commit
      // that carries it.
      setTailHeight(plan.tail)
      return
    }

    landing.current = false
    scrollTo(element, plan.scroll)
  })

  // The answer arriving. While a question is pinned the spacer gives back
  // exactly the height the answer took, so the transcript does not move at all;
  // when there is nothing left to give back, the bottom takes over.
  useEffect(() => {
    const element = container.current
    if (!element) return

    // A pin still landing owns the spacer. Recomputing it here on the same
    // commit would measure a DOM that does not carry the new spacer yet and ask
    // for it twice over — a spacer of double the height, and a scrollbar that
    // lurches before settling back.
    if (landing.current) return

    if (tailHeight.current > 0) {
      const next = step().tail
      setTailHeight(next)
      if (next === 0) pinned.current = false
      return
    }

    if (pinned.current || !following.current) return
    // Assigned rather than animated. A smooth scroll per delta turns a fast
    // answer into a moving target, and it is motion nobody asked for.
    element.scrollTop = element.scrollHeight
    // Every event the live Turn applies produces a new projection, so this is
    // one dependency for every way the transcript can get taller: a delta, a
    // tool call joining the list, a status line under an answer that ended.
  }, [desk.entries, step, setTailHeight])

  function onScroll() {
    const element = container.current
    if (!element) return
    // A pinned question owns the scroll position, and the browser reports the
    // pin itself as a scroll. Only the reader releases it (`onUserScroll`).
    if (pinned.current) return
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight
    following.current = distance <= FOLLOW_THRESHOLD_PX
  }

  /** The reader taking the scroll back. A wheel or a drag outranks the pin. */
  function onUserScroll() {
    pinned.current = false
    landing.current = false
  }

  // A new conversation opens on the greeting and the composer, centred.
  // Both guards are needed: no Thread means nothing has been asked yet, and no
  // entries means the pending question a submit puts in the transcript before
  // the server hands back a Thread id still routes to the transcript branch
  // rather than flashing back onto the greeting for a frame. A reopened Thread
  // that arrives with no entries yet keeps its non-null id, so its history
  // fade-in also never sees the greeting. The transcript's own hooks above
  // still run — they all early-return on a null container ref — so React's
  // hook order stays stable across this branch.
  if (desk.threadId === null && desk.entries.length === 0) {
    return (
      <div
        key="chat-opening"
        className="scrollbar-thin flex min-h-0 flex-1 items-center justify-center overflow-y-auto px-5 pb-16 pt-5 motion-safe:animate-vg-fade-in"
      >
        {/* Narrower than the docked composer's 760 on purpose. The opening is
            one field under one line of type, and a field that runs the full
            width of the transcript reads as a page rather than as a prompt.
            What the opening gets instead of width is height — see the card. */}
        <div className="w-full max-w-[680px]">
          <Greeting />
          <div className="mt-5">
            <Composer variant="opening" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <>
      <div
        ref={container}
        onScroll={onScroll}
        onWheel={onUserScroll}
        onTouchMove={onUserScroll}
        onClick={() => dispatch({ type: "overlay", overlay: null })}
        className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-[190px] pt-2"
      >
        <div className="mx-auto w-full max-w-[760px] space-y-7 py-5">
          {desk.entries.map((entry, index) => {
            if (entry.kind === "user") {
              // Only the newest question is an anchor. `ref` is never cleared on
              // unmount: a pending question and the committed one that replaces
              // it hand over in that order, and nulling would leave the pin
              // pointing at nothing for the render in between.
              const isAnchor = index === lastQuestionIndex
              return (
                <UserMessage
                  key={entry.key}
                  text={entry.text}
                  pending={entry.pending}
                  attachments={entry.attachments}
                  innerRef={
                    isAnchor
                      ? (element) => {
                          if (element) anchor.current = element
                        }
                      : undefined
                  }
                />
              )
            }

            if (entry.kind === "assistant") {
              return (
                <AssistantMessage
                  key={entry.key}
                  view={entry.view}
                  messageId={entry.messageId}
                  flaggedReason={entry.flaggedReason}
                  flagFailed={entry.messageId === desk.flagFailedFor}
                  helpful={entry.helpful}
                  onFlag={desk.flag}
                  onUnflag={desk.unflag}
                  onHelpful={desk.helpful}
                  onCopy={copyText}
                  onShare={() => dispatch({ type: "overlay", overlay: "share" })}
                  // Regenerating an answer is asking its question again, so it
                  // goes out as the question rather than as a reference to the
                  // answer: `resend` already knows whether that is a retry of a
                  // Turn that ended badly or a fresh ask.
                  onRegenerate={() => {
                    const asked = questionBefore(desk.entries, entry.key)
                    if (asked !== null) desk.resend(asked.text, asked.attachments)
                  }}
                  onFollowUp={desk.submit}
                  onOpenSources={(messageId) =>
                    dispatch({ type: "open-sources", messageId })
                  }
                />
              )
            }

            return (
              <DraftMessage
                key={entry.key}
                entry={entry}
                onRetry={desk.retry}
              />
            )
          })}
        </div>

        {/* The room a pinned question needs and the transcript does not have
            yet. It shrinks as the answer arrives and is gone by the time the
            answer is taller than the screen, so it never leaves dead space
            under a finished conversation — and it sits outside the stack above
            so that at zero height it contributes no gap either. */}
        <div aria-hidden="true" style={{ height: tail }} />
      </div>

      <DockedFooter />
    </>
  )
}

/**
 * The composer, anchored to the main column rather than to the viewport.
 *
 * It follows the inspector: a composer that stayed put would slide under the
 * panel the moment it opened. Extracted because two openings dock it — the
 * transcript and the desk's empty column — and a second copy of the gradient,
 * the refusal banner and the disclaimer is two places for one footer to drift.
 *
 * `starters` offers the desk's opening questions above the field. Only the
 * empty desk column passes it: once there is an answer in the transcript the
 * questions worth asking next come from that answer, and they are already drawn
 * under it.
 *
 * `anchored` is what the transcript needs and an empty column does not. Over a
 * transcript the footer floats, so the last answer stays visually continuous
 * with the field asking the next question and a gradient hides the text running
 * under it. With nothing to scroll there is nothing to float over: it sits in
 * the column as the last flex row, which is also the only way the region above
 * it can centre anything — a floating footer's height is not a number the
 * layout above it can know, and reserving a guess for it puts the headline off
 * centre by however much the guess was wrong.
 */
function DockedFooter({ anchored = true }: { anchored?: boolean }) {
  const desk = useDesk()
  const { state, panelWidth } = useShell()

  return (
    <div
      style={anchored ? { right: panelWidth } : undefined}
      className={cn(
        "px-5 pb-3",
        anchored
          ? cn(
              "absolute bottom-0 left-0 bg-gradient-to-t from-background from-[62%] to-transparent",
              state.dragging
                ? "transition-none"
                : "transition-[right] duration-panel ease-panel",
            )
          : "flex-none",
      )}
    >
      <div className="mx-auto w-full max-w-[760px]">
        {desk.refusal && (
          <div
            role="alert"
            className="mx-2.5 mb-[-8px] flex items-start gap-2 rounded-t-[14px] border border-b-0 border-destructive/40 bg-destructive/[0.07] px-3.5 pb-4 pt-2.5 text-meta text-destructive"
          >
            <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
            <p className="min-w-0 flex-1">
              {desk.refusal}
              {/* The banner used to end here, so the most common way to lose
                  a question — a session that expired between opening the tab
                  and pressing send — was a red sentence with nothing to press
                  and a draft the reader had to copy out by hand. The route
                  out comes from the classification beside the message. */}
              {desk.refusalFailure?.recovery === "signin" && (
                  <Link
                    href="/login"
                    className="ml-1.5 rounded-sm font-medium underline underline-offset-2 hover:brightness-110 focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  >
                    {desk.refusalFailure.action}
                  </Link>
                )}
            </p>
            <IconButton
              label="Đóng thông báo"
              size="sm"
              onClick={desk.dismissRefusal}
              className="size-5 text-destructive hover:bg-destructive/15 hover:text-destructive"
            >
              <X className="size-3.5" />
            </IconButton>
          </div>
        )}

        <Composer />

        <div>
          <p className="min-h-0 overflow-hidden pt-2.5 text-center text-micro text-ink-6">
            VisgniteAI có thể sai sót. Hãy đối chiếu nguồn dữ liệu trước khi ra quyết định đầu tư.
          </p>
        </div>
      </div>
    </div>
  )
}

/**
 * Move the transcript, smoothly where the reader has not asked otherwise.
 *
 * `scrollTo` is the only way to ask for a smooth scroll, and it is missing in
 * jsdom, so the assignment stays as the fallback: the position matters and the
 * animation does not.
 */
function scrollTo(element: HTMLElement, top: number): void {
  const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  if (typeof element.scrollTo !== "function") {
    element.scrollTop = top
    return
  }
  element.scrollTo({ top, behavior: still ? "auto" : "smooth" })
}

/**
 * One question the user asked, and the three things they can do with it again.
 *
 * The actions sit under the bubble and appear on hover or on focus. Copy is the
 * text itself; Sửa offers it back to the composer *unsent*, which is the same
 * contract a question offered by a panel has (`shell-state`, `ask`); Gửi lại
 * asks it again, and on the last question of a Turn that ended badly that is a
 * linked retry rather than a fresh Turn (`desk-state`, `resend`).
 *
 * **Sửa edits nothing.** A message is immutable in the store, so putting the
 * sentence back in the field is the honest version of editing it: what leaves
 * is a new question, and the one already asked stays in the transcript where
 * the answer under it can still be read against it.
 *
 * The row is mounted always and revealed with opacity — mounting on hover puts
 * it out of reach of a keyboard, and makes it appear under a pointer that had
 * already arrived.
 */
function UserMessage({
  text,
  pending,
  attachments,
  innerRef,
}: {
  text: string
  pending: boolean
  /** What this question carried. Drawn above the bubble, aligned with it. */
  attachments: Attachment[]
  /** Set on the newest question, which the transcript pins to the top. */
  innerRef?: (element: HTMLDivElement | null) => void
}) {
  const desk = useDesk()
  const { dispatch } = useShell()
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), 1600)
    return () => window.clearTimeout(timer)
  }, [copied])

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
    } catch {
      // A browser that refuses the clipboard — no permission, an insecure
      // origin — is not something to report as an error over one sentence the
      // user can still select by hand.
    }
  }

  return (
    <div ref={innerRef} className="group/msg flex flex-col items-end gap-1">
      {/* Above the question and right-aligned with it, so the files read as
          part of what was asked rather than as a separate event. No remove
          button: a question already sent cannot have a file taken out of it,
          and a control that would only ever refuse is worse than none. */}
      {attachments.length > 0 && (
        <div className="flex max-w-[82%] flex-wrap justify-end gap-1.5 pb-0.5">
          {attachments.map((attachment) => (
            <AttachmentChip
              key={attachment.id}
              filename={attachment.filename}
              byteSize={attachment.byte_size}
              image={isImageAttachment(attachment)}
              // The row is immutable, so the browser may cache these for the
              // life of the tab. That is why this is a URL and not a fetch.
              previewUrl={
                isImageAttachment(attachment) ? attachmentUrl(attachment.id) : undefined
              }
            />
          ))}
        </div>
      )}

      {/* The question is the one thing in a bubble, and it is the bubble
          surface rather than the muted one: on this ground `bg-muted` sits a
          percent off the page and stops reading as a bubble at all. */}
      <p
        className={cn(
          "max-w-[82%] animate-vg-message-in whitespace-pre-wrap rounded-2xl bg-surface-bubble px-[1.05em] py-[0.7em] text-[0.95rem] leading-[1.5] text-foreground",
          pending && "opacity-70",
        )}
      >
        {text}
      </p>

      {/* Nothing to act on until the question exists on the backend: a pending
          bubble is a sentence this tab has not yet been told was written. */}
      {!pending && (
        <div className="flex items-center gap-0.5 pr-1 opacity-0 transition-opacity focus-within:opacity-100 group-hover/msg:opacity-100">
          <IconButton label={copied ? "Đã sao chép" : "Sao chép"} size="sm" onClick={() => void copy()}>
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          </IconButton>
          <IconButton
            label="Sửa câu hỏi"
            size="sm"
            onClick={() => dispatch({ type: "ask", text })}
          >
            <Pencil className="size-3.5" />
          </IconButton>
          <IconButton
            label="Gửi lại"
            size="sm"
            // A Turn is running: the composer offers Stop rather than Send for
            // this stretch, and this control says the same thing by going inert.
            disabled={desk.canCancel}
            // Its own attachments, because this control re-asks *this*
            // question: the ids are on the message the button sits under.
            onClick={() =>
              desk.resend(
                text,
                attachments.map((attachment) => attachment.id),
              )
            }
          >
            <RotateCcw className="size-3.5" />
          </IconButton>
        </div>
      )}
    </div>
  )
}
