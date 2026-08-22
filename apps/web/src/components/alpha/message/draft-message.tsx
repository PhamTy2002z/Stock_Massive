"use client"

import { Loader2 } from "lucide-react"

import type { DraftEntry } from "@/lib/alpha-desk/transcript"
import { Markdown } from "./markdown"
import { MessageShell } from "./message-shell"
import { ToolCallList } from "./tool-call-list"
import { TurnStatus } from "./turn-status"

/**
 * The Turn in flight, as far as it has got.
 *
 * The same two things the canonical message shows, in the same order, so the
 * swap at the terminal event moves nothing on screen.
 *
 * What it carries is everything the user has already been shown, through every
 * ending. Cancel keeps it, a deadline keeps it, a failed route keeps it — the
 * status is a line underneath, never a replacement.
 */
export function DraftMessage({
  entry,
  onRetry,
  className,
}: {
  entry: DraftEntry
  onRetry: () => void
  className?: string
}) {
  const running =
    entry.phase === "starting" || entry.phase === "running" || entry.phase === "cancelling"

  return (
    <MessageShell className={className}>
      <ToolCallList calls={entry.toolCalls} />

      {/* Rendered as the Markdown it is, mid-sentence and all: the answer
          arrives as deltas, so a closing marker can be one delta behind the
          text it closes. A syntax character on screen for a moment is the price
          of the answer arriving as it is written, and holding the text back
          until it parsed cleanly would be the buffered transport this whole
          path exists to avoid. */}
      {entry.text !== "" && <Markdown text={entry.text} />}

      {/* Before the first delta and before the first call. The harness has to
          look like it is working rather than hung, and the first thing the
          backend sends can be a moment away. */}
      {running && entry.text === "" && entry.toolCalls.length === 0 && (
        <p role="status" className="flex items-center gap-2 text-meta text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin motion-reduce:animate-none" />
          Đang chuẩn bị…
        </p>
      )}

      <TurnStatus
        phase={entry.phase}
        terminalReason={entry.terminalReason}
        onRetry={onRetry}
      />
    </MessageShell>
  )
}
