"use client"

import { useState, type FormEvent, type KeyboardEvent } from "react"
import { Send, Square } from "lucide-react"

import { CANCELLING_LABEL } from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"

/**
 * Where the user says something.
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

  function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || canCancel || isSubmitting) return
    onSend(trimmed)
    setText("")
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
      className={cn("flex items-end gap-2 border-t border-border/60 bg-background p-3", className)}
    >
      <div className="min-w-0 flex-1 space-y-1">
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          aria-label="Ask Alpha Desk"
          placeholder={
            activeSymbol
              ? `Ask about ${activeSymbol}, or any Universe symbol…`
              : "Ask about any Universe symbol…"
          }
          className="max-h-40 min-h-[2.5rem] w-full resize-y rounded-md border border-border/60 bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>

      {canCancel ? (
        <button
          type="button"
          onClick={onCancel}
          disabled={isCancelling}
          className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-md border border-border/60 px-3 text-sm hover:bg-muted disabled:opacity-50"
        >
          <Square className="h-3.5 w-3.5" />
          {isCancelling ? CANCELLING_LABEL : "Stop"}
        </button>
      ) : (
        <button
          type="submit"
          disabled={!text.trim() || isSubmitting}
          className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Send className="h-3.5 w-3.5" />
          Send
        </button>
      )}
    </form>
  )
}
