"use client"

import { AlertCircle, Check, Loader2 } from "lucide-react"

import { TOOL_CALL_COPY, toolCallErrorLabel } from "@/lib/alpha-desk/copy"
import type { ToolCall } from "@/lib/alpha-desk/types"
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
          <StatusIcon status={call.status} />
          <span className="min-w-0 flex-1 truncate">{call.summary}</span>
          <span className={cn("shrink-0 text-micro", call.status === "error" && "text-destructive")}>
            {call.status === "error"
              ? toolCallErrorLabel(call.error)
              : TOOL_CALL_COPY[call.status]}
          </span>
        </li>
      ))}
    </ul>
  )
}

function StatusIcon({ status }: { status: ToolCall["status"] }) {
  if (status === "running") {
    return <Loader2 className="size-3 shrink-0 animate-spin motion-reduce:animate-none" />
  }
  if (status === "error") {
    return <AlertCircle className="size-3 shrink-0 text-destructive" />
  }
  return <Check className="size-3 shrink-0" />
}
