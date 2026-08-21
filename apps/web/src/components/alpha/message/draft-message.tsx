"use client"

import { Loader2 } from "lucide-react"

import type { DraftEntry } from "@/lib/alpha-desk/transcript"
import { ContentBlockView } from "./content-block"
import { MessageShell } from "./message-shell"
import { SearchProgress, hasVisibleTrail } from "./search-progress"
import { TurnStatus } from "./turn-status"

/**
 * The Turn in flight, as far as it has got.
 *
 * The draft is not history and never carries the Risk Notice: the notice is
 * attached in the terminal transaction, and the canonical message that arrives
 * a moment later is what replaces this. Synthesising one here would put a
 * backend-owned guarantee under the client's control, which is the thing
 * attaching it in the backend exists to prevent.
 *
 * What it does carry is everything the user has already been shown, through
 * every ending. Cancel keeps it, a deadline keeps it, a failed route keeps it —
 * the status is a line underneath, never a replacement.
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
  const livePhase = running ? entry.activity : null
  // The trail outlives the running state. What the Turn did before it ended is
  // still what it did, and on a Turn that stopped early it is most of what the
  // reader has to go on — but only where there is a step left worth naming,
  // which is the trail's own question to answer rather than this one's.
  const showsActivity = hasVisibleTrail(entry.steps, livePhase)

  return (
    <MessageShell className={className}>
      {/* Above the blocks and open while the work happens: the reader is
          watching a list grow, and a trail under the answer would put the
          growing part below the thing they are waiting for. It folds itself
          away as soon as the first block lands, because from that moment the
          answer is what the reader is here for. */}
      {showsActivity && (
        <SearchProgress
          steps={entry.steps}
          activity={livePhase}
          ending={running ? null : entry.phase === "completed" ? "done" : "stopped"}
          answered={entry.blocks.length > 0}
          defaultOpen
        />
      )}

      {/* `appendedIndex` is exactly the block the last event delivered, and it
          is the only block that cascades its prose in (`word-cadence`). A
          snapshot appends nothing, so a reconnect and a reopened Thread stage
          nothing and everything present renders at once. */}
      {entry.blocks.map((block, index) => (
        <ContentBlockView
          key={`block-${index}`}
          block={block}
          stagger={index === entry.appendedIndex}
        />
      ))}

      {/* Before the first activity or block. The harness has to look like it is
          working rather than hung, and the first thing the backend sends can be
          a moment away. */}
      {running && !showsActivity && entry.blocks.length === 0 && (
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
