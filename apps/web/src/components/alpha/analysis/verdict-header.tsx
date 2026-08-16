"use client"

import type { AnalysisArtifact } from "@/lib/alpha-desk/analysis"
import { cn } from "@/lib/utils"
import { CHROME } from "./copy"

/**
 * The verdict, pinned.
 *
 * One scalar — `accumulate | hold | reduce | avoid | watch` — because the rail
 * reads it as an extracted column and shows one word for ten symbols
 * (`docs/specs/0002` §5). It is the model's judgment and it is labelled as
 * such; the citation count beside it is what that judgment rests on, and it is
 * a count rather than a list because the inline treatment is bounded.
 *
 * `verdictLine` is the model's one sentence and is Vietnamese. The verdict word
 * itself, the session and the citation count are chrome.
 */
export function VerdictHeader({
  artifact,
  className,
}: {
  artifact: AnalysisArtifact
  className?: string
}) {
  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-sm font-semibold uppercase tracking-wide">
          {artifact.verdict}
        </span>
        <span className="text-xs font-medium">{artifact.symbol}</span>
        <span className="text-xs tabular-nums text-muted-foreground">
          {artifact.tradingDay}
        </span>
        <span className="text-micro tabular-nums text-muted-foreground">
          · {CHROME.citations} {artifact.citationCount}
        </span>
        {/* Several template versions are in circulation across days, so the one
            on screen is identifiable rather than assumed. */}
        <span className="text-micro text-muted-foreground">
          · {CHROME.template} v{artifact.schemaVersion}
        </span>
      </div>

      {artifact.verdictLine && (
        <p className="text-meta leading-relaxed">{artifact.verdictLine}</p>
      )}
    </div>
  )
}
