"use client"

import { answerSources } from "@/lib/alpha-desk/answer-sources"
import type { ToolCall } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"
import { SourceChips } from "./source-chips"

/**
 * The one control that says what an answer rested on, and opens the rest.
 *
 * It sits under the answer rather than in the timeline above it, because the
 * two answer different questions. The timeline is *what happened* — read while
 * waiting, folded away once the answer arrives. This is *what it rested on* —
 * read after, by somebody deciding whether to believe it.
 *
 * The count is the rows of the sources panel (`answerSources`): each source
 * once, not each call — three searches that returned the same page rested on
 * one source. The sources the answer lists at its end count too: that list is
 * not drawn under the answer, so this is where a reader finds it.
 *
 * Absent when there is nothing behind the answer. A pill reading *0 sources* is a
 * claim about an answer that never went looking, and it invites a click onto an
 * empty panel.
 */
export function SourcePill({
  toolCalls,
  text,
  onOpen,
  className,
}: {
  toolCalls: ToolCall[]
  /** The answer, whose closing source list this counts. */
  text: string
  onOpen: () => void
  className?: string
}) {
  const sources = answerSources(text, toolCalls)
  if (sources.length === 0) return null
  // One disc per mark. Rows sharing a hostname mark agree on `favicon`: it is
  // true exactly when a tool result recorded that host.
  const marks = [...new Map(sources.map((source) => [source.mark, source])).values()]

  return (
    <div className={cn("flex", className)}>
      <button
        type="button"
        onClick={onOpen}
        className="flex items-center gap-2 rounded-full border border-border bg-surface-raised py-1.5 pl-[0.55rem] pr-3.5 text-meta text-ink-3 transition-colors hover:bg-accent hover:text-foreground"
      >
        <SourceChips sources={marks} />
        {sources.length} {sources.length === 1 ? "source" : "sources"}
      </button>
    </div>
  )
}

