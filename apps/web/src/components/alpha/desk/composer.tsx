"use client"

import { useRef, useState, type FormEvent, type KeyboardEvent } from "react"
import { ArrowUp, Clock, Square } from "lucide-react"

import { CANCELLING_LABEL } from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"

/** What a question is allowed to grow to before the field starts scrolling. */
const MAX_FIELD_HEIGHT_PX = 150

/**
 * Where the user says something.
 *
 * The reference draws this as one lifted card rather than as a field with a
 * button beside it: 18px corners, a hairline, a shadow deep enough to separate
 * it from the transcript scrolling underneath, and a row of controls *inside*
 * the card. The field itself has no border of its own — it would be a second
 * box inside the first.
 *
 * The field is **never disabled by anything happening elsewhere**. A pending
 * on-demand Analysis does not touch it (`docs/specs/0002` §6), and neither does
 * a Turn in flight: composing the next question while an answer arrives is the
 * ordinary way anyone uses a conversation, and locking the box would make the
 * surface feel like a form submission.
 *
 * What changes is the control beside it. While a Turn runs it is **Stop**, and
 * a pressed Stop is immediate: the label becomes *Cancelling…* and the control
 * goes inert straight away rather than waiting for the terminal event, because
 * the user pressed it and the acknowledgement is theirs to see.
 */
export function Composer({
  onSend,
  onCancel,
  canCancel,
  isCancelling,
  isSubmitting,
  activeSymbol,
  className,
}: {
  onSend: (text: string) => void
  onCancel: () => void
  /** A Turn is running, so the control stops it rather than starting another. */
  canCancel: boolean
  isCancelling: boolean
  /** The create request is in flight. Sending twice would be two Turns. */
  isSubmitting: boolean
  /** The workspace lens, named so the user knows what "this symbol" means. */
  activeSymbol: string | null
  className?: string
}) {
  const [text, setText] = useState("")
  const field = useRef<HTMLTextAreaElement>(null)

  function resize() {
    const element = field.current
    if (!element) return
    // Measured from a collapsed height, or the box only ever grows: scrollHeight
    // of an already-tall element reports the height it was given, not the one
    // its content needs.
    element.style.height = "auto"
    element.style.height = `${Math.min(element.scrollHeight, MAX_FIELD_HEIGHT_PX)}px`
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || canCancel || isSubmitting) return
    onSend(trimmed)
    setText("")
    // The field is shrinking back to one row, so the inline height has to go
    // with it — otherwise an emptied box keeps the height of the question that
    // is no longer in it.
    if (field.current) field.current.style.height = "auto"
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter breaks the line. A multi-line question is common
    // enough here that the modifier has to do something other than nothing.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      submit(event)
    }
  }

  return (
    <form
      onSubmit={submit}
      className={cn(
        // The gradient is what lets the transcript run *under* the composer
        // rather than stop above it, which is how the reference keeps the last
        // answer visually continuous with the field asking the next question.
        "bg-gradient-to-t from-background from-[62%] to-transparent px-4 pb-3 pt-6",
        className
      )}
    >
      <div className="mx-auto w-full max-w-[760px]">
        <div className="relative rounded-composer border border-border bg-surface-sunken px-3.5 pb-2.5 pt-3 shadow-composer">
          {activeSymbol && (
            <div className="flex items-center gap-2 pb-2">
              <span className="inline-flex items-center rounded-lg border border-primary/30 bg-primary/[0.09] px-2 py-0.5 font-mono text-meta text-primary">
                {activeSymbol}
              </span>
              <span className="min-w-0 truncate text-meta text-muted-foreground">
                đang là ngữ cảnh phân tích
              </span>
            </div>
          )}

          <textarea
            ref={field}
            value={text}
            onChange={(event) => {
              setText(event.target.value)
              resize()
            }}
            onKeyDown={onKeyDown}
            rows={1}
            aria-label="Ask Alpha Desk"
            placeholder={
              activeSymbol
                ? `Ask about ${activeSymbol}, or any Universe symbol…`
                : "Ask about any Universe symbol…"
            }
            className="block max-h-[150px] min-h-[26px] w-full resize-none border-0 bg-transparent p-0 pb-2 text-[0.98rem] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground"
          />

          <div className="flex items-center gap-1.5">
            {/* States the window every answer is computed over. Inert on
                purpose: the window is a property of the Analysis, not a control
                the composer owns. */}
            <span className="hidden items-center gap-1.5 rounded-lg px-1.5 py-1 text-meta text-muted-foreground sm:flex">
              <Clock className="size-[15px]" />
              Dữ liệu 12 tháng
            </span>

            <div className="ml-auto flex items-center gap-1.5">
              {canCancel ? (
                <button
                  type="button"
                  onClick={onCancel}
                  disabled={isCancelling}
                  className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-[10px] border border-border px-3 text-control text-ink-3 transition-colors hover:bg-foreground/[0.06] hover:text-foreground disabled:opacity-50"
                >
                  <Square className="size-3.5" />
                  {isCancelling ? CANCELLING_LABEL : "Stop"}
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!text.trim() || isSubmitting}
                  className="inline-flex size-8 shrink-0 items-center justify-center rounded-[10px] bg-primary text-primary-foreground transition-[filter,transform] hover:-translate-y-px hover:brightness-110 disabled:pointer-events-none disabled:opacity-40"
                >
                  <ArrowUp className="size-[17px]" strokeWidth={2} />
                  <span className="sr-only">Send</span>
                </button>
              )}
            </div>
          </div>
        </div>

        <p className="mt-2.5 text-center text-micro text-muted-foreground">
          VisgniteAI có thể sai sót. Hãy đối chiếu nguồn dữ liệu trước khi ra quyết định đầu tư.
        </p>
      </div>
    </form>
  )
}
