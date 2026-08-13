"use client"

import { AlertTriangle, CalendarDays, CheckCircle2, Clock } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  coverageSentence,
  freshnessSentence,
  signalIssueSentences,
} from "@/lib/signal-issues"
import type { VolumeSpikeResponse } from "@/lib/api"

/**
 * The band that says which session is on screen and how much of it we can see.
 *
 * It is rendered whether or not anything is wrong. A band that only appears on
 * trouble teaches the reader that its absence means nothing was checked — so
 * the healthy case has to look like a statement, not like silence.
 */
export function CoverageBand({
  signal,
  className,
}: {
  signal: VolumeSpikeResponse
  className?: string
}) {
  const { coverage, freshness, trading_day: tradingDay, issues } = signal
  const healthy = coverage.state === "ready" && freshness === "fresh"

  return (
    <div
      role="status"
      aria-label="Độ phủ và độ mới của tín hiệu"
      className={cn(
        "rounded-lg border p-4 space-y-2",
        healthy
          ? "border-border/50 bg-card/50"
          : "border-amber-500/40 bg-amber-500/5",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <span className="inline-flex items-center gap-2">
          <CalendarDays className="h-4 w-4 text-muted-foreground" />
          <span className="text-muted-foreground">Phiên tín hiệu:</span>
          <span className="font-medium tabular-nums">
            {tradingDay ?? "chưa xác định"}
          </span>
        </span>
        <span className="inline-flex items-center gap-2">
          {coverage.state === "ready" ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          )}
          <span>
            {coverageSentence(coverage.state, coverage.evaluated, coverage.total)}
          </span>
        </span>
        <span className="inline-flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <span>{freshnessSentence(freshness)}</span>
        </span>
      </div>

      {issues.length > 0 && (
        <ul className="text-sm text-muted-foreground space-y-1">
          {signalIssueSentences(issues).map((sentence) => (
            <li key={sentence}>• {sentence}</li>
          ))}
        </ul>
      )}

      {signal.cohort_version && (
        <p className="text-xs text-muted-foreground">
          Xếp hạng lợi nhuận theo kỳ báo cáo{" "}
          {signal.cohort_version.reporting_period}
        </p>
      )}
    </div>
  )
}
