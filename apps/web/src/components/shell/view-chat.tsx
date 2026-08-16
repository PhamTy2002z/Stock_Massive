"use client"

import { useEffect, useRef, useState } from "react"
import { AlertCircle, Check, Copy, Pencil, RotateCcw, X } from "lucide-react"

import { AnalysisCard } from "@/components/alpha/analysis"
import { AssistantMessage } from "@/components/alpha/message/assistant-message"
import { DraftMessage } from "@/components/alpha/message/draft-message"
import { cn } from "@/lib/utils"

import { Composer } from "./composer"
import { useDesk } from "./desk-state"
import { IconButton } from "./primitives"
import { useShell } from "./shell-state"

/** How close to the bottom still counts as "following" the newest content. */
const FOLLOW_THRESHOLD_PX = 120

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
 */
export function ChatView() {
  const desk = useDesk()
  const { state, dispatch, panelWidth } = useShell()
  const container = useRef<HTMLDivElement>(null)
  const following = useRef(true)

  const last = desk.entries.at(-1)
  const blockCount = last?.kind === "draft" ? last.blocks.length : 0

  useEffect(() => {
    const element = container.current
    if (!element || !following.current) return
    // Assigned rather than animated. A smooth scroll per block turns a fast
    // answer into a moving target, and it is motion nobody asked for.
    element.scrollTop = element.scrollHeight
  }, [desk.entries.length, blockCount])

  function onScroll() {
    const element = container.current
    if (!element) return
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight
    following.current = distance <= FOLLOW_THRESHOLD_PX
  }

  return (
    <>
      <div
        ref={container}
        onScroll={onScroll}
        onClick={() => dispatch({ type: "overlay", overlay: null })}
        className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-[190px] pt-2"
      >
        <div className="mx-auto w-full max-w-[760px] space-y-7 py-5">
          {desk.entries.map((entry) => {
            if (entry.kind === "user") {
              return <UserMessage key={entry.key} text={entry.text} pending={entry.pending} />
            }

            if (entry.kind === "assistant") {
              return (
                <AssistantMessage
                  key={entry.key}
                  view={entry.view}
                  messageId={entry.messageId}
                  flaggedReason={entry.flaggedReason}
                  flagFailed={entry.messageId === desk.flagFailedFor}
                  onFlag={desk.flag}
                  onUnflag={desk.unflag}
                />
              )
            }

            if (entry.kind === "analysis") {
              return (
                <AnalysisCard
                  key={entry.key}
                  symbol={entry.symbol}
                  tradingDay={entry.tradingDay}
                />
              )
            }

            return <DraftMessage key={entry.key} entry={entry} onRetry={desk.retry} />
          })}
        </div>
      </div>

      {/* Anchored to the main column rather than the viewport, and it follows
          the inspector: a composer that stayed put would slide under the panel
          the moment it opened. */}
      <div
        style={{ right: panelWidth }}
        className={cn(
          "absolute bottom-0 left-0 bg-gradient-to-t from-background from-[62%] to-transparent px-5 pb-3",
          state.dragging ? "transition-none" : "transition-[right] duration-panel ease-panel",
        )}
      >
        <div className="mx-auto w-full max-w-[760px]">
          {desk.refusal && (
            <div
              role="alert"
              className="mx-2.5 mb-[-8px] flex items-start gap-2 rounded-t-[14px] border border-b-0 border-destructive/40 bg-destructive/[0.07] px-3.5 pb-4 pt-2.5 text-meta text-destructive"
            >
              <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
              <p className="min-w-0 flex-1">{desk.refusal}</p>
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

          {!desk.refusal && !state.noticeDismissed && <SnapshotNotice />}

          <Composer />

          <p className="mt-2.5 text-center text-micro text-ink-6">
            VisgniteAI có thể sai sót. Hãy đối chiếu nguồn dữ liệu trước khi ra quyết định đầu tư.
          </p>
        </div>
      </div>
    </>
  )
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
function UserMessage({ text, pending }: { text: string; pending: boolean }) {
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
    <div className="group/msg flex flex-col items-end gap-1">
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
            onClick={() => desk.resend(text)}
          >
            <RotateCcw className="size-3.5" />
          </IconButton>
        </div>
      )}
    </div>
  )
}

/**
 * The one standing caveat about the data behind every answer.
 *
 * Tucked under the composer's top edge rather than floated above it, so the two
 * read as one object: the notice is a property of what the field is about to
 * ask, not a separate alert competing with it.
 */
function SnapshotNotice() {
  const { dispatch } = useShell()
  return (
    <div className="mx-2.5 mb-[-8px] flex items-center gap-2.5 rounded-t-[14px] border border-b-0 border-border bg-surface-menu px-3.5 pb-4 pt-2.5 text-control text-ink-4">
      <i aria-hidden="true" className="block size-[5px] shrink-0 rounded-full bg-caution" />
      <span className="min-w-0 flex-1">
        Câu trả lời dựa trên dữ liệu đã chốt phiên, không phải giá khớp lệnh thời gian thực.
      </span>
      <IconButton
        label="Ẩn thông báo"
        size="sm"
        onClick={() => dispatch({ type: "dismiss-notice" })}
        className="size-6"
      >
        <X className="size-3.5" strokeWidth={1.8} />
      </IconButton>
    </div>
  )
}
