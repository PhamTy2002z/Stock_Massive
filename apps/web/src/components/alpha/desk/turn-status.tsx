"use client"

import { Info, Loader2, RotateCw } from "lucide-react"

import { CANCELLING_LABEL, terminalSentence } from "@/lib/alpha-desk/copy"
import type { LivePhase } from "@/lib/alpha-desk/live-turn"
import { cn } from "@/lib/utils"

/**
 * How a Turn ended, as a line under whatever it produced.
 *
 * **Never a full-screen error** (`docs/specs/0002` §6). A Turn that ran out of
 * budget, hit its deadline or lost its route still produced prose that passed
 * the Gate, and replacing that with an error page would throw away the only
 * part the user wanted. So this is an inline note beside the content, and the
 * content is rendered by the caller either way.
 *
 * Retry starts a **new** Turn. The one described here stays exactly as it is —
 * its spend, its message and its traces are immutable — which is why the
 * control says "Retry" and not "Try again", and why nothing here clears the
 * blocks above it.
 */
export function TurnStatus({
  phase,
  terminalReason,
  onRetry,
  className,
}: {
  phase: LivePhase
  terminalReason: string | null
  onRetry: () => void
  className?: string
}) {
  if (phase === "cancelling") {
    return (
      <p
        role="status"
        className={cn(
          "flex items-center gap-2 text-xs text-muted-foreground",
          className,
        )}
      >
        <Loader2 className="h-3 w-3 animate-spin motion-reduce:animate-none" />
        {CANCELLING_LABEL}
      </p>
    )
  }

  // `completed` is the ordinary end and says nothing; the answer is the status.
  if (phase !== "incomplete" && phase !== "failed" && phase !== "cancelled") {
    return null
  }

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-3 py-2 text-xs",
        className,
      )}
    >
      <Info className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <span role="status" className="min-w-0 flex-1 text-muted-foreground">
        {terminalSentence(phase === "cancelled" ? "cancelled_by_user" : terminalReason)}
      </span>
      {/* No pending state of its own: pressing it starts a Turn, and a started
          Turn is not terminal, so this whole block is gone by the next render.
          A spinner here would be a second source of truth about the same fact. */}
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border/60 bg-background px-2 py-1 hover:bg-muted"
      >
        <RotateCw className="h-3 w-3" />
        Retry
      </button>
    </div>
  )
}
