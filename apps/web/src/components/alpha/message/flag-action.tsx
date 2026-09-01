"use client"

import { useEffect, useRef, useState } from "react"
import { Flag } from "lucide-react"

import { FLAG_COPY, FLAG_REASONS, FLAG_REASON_LABELS } from "@/lib/alpha-desk/copy"
import type { FlagReason } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"

/**
 * Flag a message — the one dispute action v1 ships.
 *
 * **It promises nothing, and that is the design rather than an omission.** V1
 * has no dispute workflow: pressing this opens no ticket, notifies nobody and
 * suspends no account. So the acknowledgement says what was recorded and stops.
 * A "we'll get back to you" here would be a promise with no mechanism behind
 * it, and a reader waiting for a reply that is never coming is worse off than
 * one told plainly what the action does.
 *
 * **One flag per message.** Choosing a second reason replaces the first rather
 * than adding to it, because the backend writes a pair of nullable columns and
 * not rows in a `message_flag` table it deliberately does not have. The menu
 * therefore shows the current reason as chosen rather than offering to add
 * another.
 *
 * **Hand-rolled rather than a `DropdownMenu`.** The one behaviour that matters
 * is that four labelled choices are reachable and that the control is quiet
 * underneath an answer; a portalled menu primitive would bring a focus trap and
 * an overlay to a control the size of an icon, and would put the assertion that
 * the four reasons are offered behind a portal in every test that makes it.
 */
export function FlagAction({
  messageId,
  reason,
  failed = false,
  onFlag,
  onUnflag,
  className,
}: {
  messageId: number
  /** The reason already stored on this message, or null. */
  reason: FlagReason | null
  /** The last write against *this* message was rejected. Never optimistic. */
  failed?: boolean
  onFlag: (messageId: number, reason: FlagReason) => void
  onUnflag: (messageId: number) => void
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const container = useRef<HTMLDivElement>(null)

  // A press anywhere else closes it. Without this the menu would survive the
  // reader scrolling on to the next answer and clicking something there.
  useEffect(() => {
    if (!open) return
    function onPointerDown(event: MouseEvent) {
      if (!container.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("mousedown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [open])

  function choose(next: FlagReason) {
    setOpen(false)
    onFlag(messageId, next)
  }

  function clear() {
    setOpen(false)
    onUnflag(messageId)
  }

  return (
    <div ref={container} className={cn("relative flex flex-col gap-1", className)}>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen((was) => !was)}
          aria-haspopup="menu"
          aria-expanded={open}
          // Unobtrusive: an icon that gains its label only to a screen reader
          // and to a pointer that rests on it. An answer is for reading, and a
          // full-width "Was this helpful?" bar under every one of them is the
          // thing this must not become.
          aria-label={FLAG_COPY.action}
          title={FLAG_COPY.action}
          className={cn(
            "inline-flex items-center gap-1 rounded-md p-1 text-meta text-muted-foreground transition-colors",
            "hover:bg-foreground/[0.06] hover:text-foreground",
            reason !== null && "text-caution",
          )}
        >
          <Flag className="h-3.5 w-3.5" aria-hidden />
        </button>

        {failed ? (
          // The write was rejected, so nothing was recorded and the surface
          // says so. Announced, because the reader pressed something and the
          // answer is that it did not take.
          <p role="alert" className="min-w-0 text-meta text-destructive">
            {FLAG_COPY.failed}
          </p>
        ) : (
          reason !== null && (
            <p className="min-w-0 text-meta text-muted-foreground">
              <span className="font-medium text-foreground">
                {FLAG_REASON_LABELS[reason]}
              </span>
              {" — "}
              {/* States what was recorded, and stops. No ticket number, no
                  deadline, and nothing about anybody getting back to them. */}
              {FLAG_COPY.acknowledged}
            </p>
          )
        )}
      </div>

      {open && (
        <div
          role="menu"
          aria-label={FLAG_COPY.prompt}
          className="absolute left-0 top-7 z-10 w-56 rounded-[14px] border border-border bg-popover p-1.5 shadow-menu"
        >
          <p className="px-2.5 py-1.5 text-meta text-muted-foreground">{FLAG_COPY.prompt}</p>

          {FLAG_REASONS.map((candidate) => (
            <button
              key={candidate}
              type="button"
              role="menuitemradio"
              aria-checked={candidate === reason}
              onClick={() => choose(candidate)}
              className={cn(
                "flex w-full items-center rounded-[9px] px-2.5 py-2 text-left text-meta transition-colors hover:bg-foreground/[0.06]",
                candidate === reason && "font-medium text-foreground",
              )}
            >
              {FLAG_REASON_LABELS[candidate]}
            </button>
          ))}

          {reason !== null && (
            <button
              type="button"
              role="menuitem"
              onClick={clear}
              className="mt-1 flex w-full items-center rounded-lg border-t border-border px-2.5 pb-1.5 pt-2 text-left text-meta text-muted-foreground transition-colors hover:bg-foreground/[0.06] hover:text-foreground"
            >
              {FLAG_COPY.remove}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
