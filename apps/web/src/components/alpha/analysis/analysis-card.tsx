"use client"

import { useEffect, useMemo } from "react"
import { Loader2 } from "lucide-react"

import { useAnalysis, useMarkAnalysisOpened } from "@/hooks/use-analysis"
import { buildArtifact } from "@/lib/alpha-desk/analysis"
import { cn } from "@/lib/utils"
import { AnalysisArtifact } from "./analysis-artifact"
import { NARRATION } from "./copy"

/**
 * One Analysis, read and rendered where the user opened it.
 *
 * **Opening this is what advances the badge.** `last_seen_analysis_date` moves
 * for this symbol and this session only — not on app open, which would clear
 * the badge for all ten symbols at once and make the indicator meaningless
 * exactly when it has work to do (`docs/specs/0002` §3). That is why the
 * mutation fires from here, from a component that exists because a specific
 * Analysis was opened, rather than from the rail or from a layout effect.
 *
 * The read endpoints are A2's and are already cached indefinitely: an Analysis
 * is immutable once published, so a second look at last Tuesday's is the same
 * bytes and costs nothing.
 */
export function AnalysisCard({
  symbol,
  tradingDay,
  className,
}: {
  symbol: string
  tradingDay: string
  className?: string
}) {
  const analysis = useAnalysis(symbol, tradingDay)
  const { mutate: reportOpened } = useMarkAnalysisOpened()

  useEffect(() => {
    reportOpened({ symbol, tradingDay })
  }, [symbol, tradingDay, reportOpened])

  const artifact = useMemo(
    () => (analysis.data ? buildArtifact(analysis.data) : null),
    [analysis.data],
  )

  if (artifact === null) {
    return (
      <p
        className={cn(
          "flex items-center gap-2 rounded-lg border border-border/60 px-3 py-2 text-xs text-muted-foreground",
          className,
        )}
      >
        {analysis.isPending ? (
          <>
            <Loader2 className="h-3 w-3 animate-spin" /> {NARRATION.loading}
          </>
        ) : (
          NARRATION.missing
        )}
      </p>
    )
  }

  return <AnalysisArtifact artifact={artifact} className={className} />
}
