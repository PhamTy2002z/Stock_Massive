"use client"

import { AlertCircle, Check, Loader2 } from "lucide-react"

import { TOOL_CALL_COPY, toolCallErrorLabel } from "@/lib/alpha-desk/copy"
import { toolCallFailed, toolCallWaiting, type ToolCall } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"

/**
 * The tool calls behind an answer, as a list above it.
 *
 * Above the prose because that is the order the work happened in, and because a
 * list that grew *under* the thing the reader is waiting for would keep pushing
 * the answer down the page while they read it.
 *
 * One component for the draft and for the canonical message, so a call reads
 * the same before and after the swap at the terminal event: the running list
 * and the stored list are the same rows, and the only difference is that the
 * stored ones have all finished.
 *
 * The sentence on each row is the backend's `summary`. Nothing here composes
 * one out of arguments — a client that described a call would be guessing at
 * what it was for, and the guess would be what the reader believes.
 */
export function ToolCallList({
  calls,
  className,
}: {
  calls: ToolCall[]
  className?: string
}) {
  if (calls.length === 0) return null

  return (
    <ul
      aria-label={TOOL_CALL_COPY.label}
      className={cn("grid gap-1 text-meta text-muted-foreground", className)}
    >
      {calls.map((call) => (
        <li key={call.id} className="flex items-center gap-2">
          <StatusIcon call={call} />
          <span className="min-w-0 flex-1 truncate">{call.summary}</span>
          <span className={cn("shrink-0 text-micro", toolCallFailed(call) && "text-destructive")}>
            {toolCallFailed(call)
              ? toolCallErrorLabel(call.error)
              : TOOL_CALL_COPY[call.status]}
          </span>
        </li>
      ))}
    </ul>
  )
}

/**
 * The mark beside one call: still out, came back, or came back with nothing.
 *
 * Three icons for five statuses, because the reader is being told which of the
 * three happened. Which *kind* of failure it was, and which kind of wait, is the
 * word beside it — a second glyph for a call refused by a permission rule would
 * be a distinction drawn twice and read once.
 */
function StatusIcon({ call }: { call: ToolCall }) {
  if (toolCallWaiting(call)) {
    return <Loader2 className="size-3 shrink-0 animate-spin motion-reduce:animate-none" />
  }
  if (toolCallFailed(call)) {
    return <AlertCircle className="size-3 shrink-0 text-destructive" />
  }
  return <Check className="size-3 shrink-0" />
}
