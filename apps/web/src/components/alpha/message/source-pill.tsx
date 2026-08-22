"use client"

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
 * The count is of distinct pages and not of calls: three searches that all
 * returned the same newspaper rested on one source, and saying "3" there would
 * overstate how much the answer was corroborated by. That is the whole reason
 * this counts rather than summing `result_count`.
 *
 * Absent when there is nothing behind the answer. A pill reading *0 nguồn* is a
 * claim about an answer that never went looking, and it invites a click onto an
 * empty panel.
 */
export function SourcePill({
  toolCalls,
  onOpen,
  className,
}: {
  toolCalls: ToolCall[]
  onOpen: () => void
  className?: string
}) {
  const domains = distinctDomains(toolCalls)
  if (domains.length === 0) return null

  return (
    <div className={cn("flex", className)}>
      <button
        type="button"
        onClick={onOpen}
        className="flex items-center gap-2 rounded-full border border-border bg-surface-raised py-1.5 pl-[0.55rem] pr-3.5 text-meta text-ink-3 transition-colors hover:bg-accent hover:text-foreground"
      >
        <SourceChips sources={domains} />
        {domains.length} nguồn
      </button>
    </div>
  )
}

/**
 * Every distinct page behind these calls, in the order they were first seen.
 *
 * Order matters because the chips show only the first few: the earliest source
 * is the one the answer leaned on first, which is a better thing to show than
 * whichever happened to sort first.
 */
function distinctDomains(toolCalls: ToolCall[]): string[] {
  const seen = new Set<string>()
  const domains: string[] = []
  for (const call of toolCalls) {
    for (const result of call.results) {
      const domain = result.source.trim()
      if (domain === "" || seen.has(domain)) continue
      seen.add(domain)
      domains.push(domain)
    }
  }
  return domains
}
