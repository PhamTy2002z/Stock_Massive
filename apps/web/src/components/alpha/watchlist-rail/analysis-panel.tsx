"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"

import { useAnalysis, useAnalysisHistory, useMarkAnalysisOpened } from "@/hooks/use-analysis"
import type { AnalysisDetail } from "@/lib/alpha"
import { cn } from "@/lib/utils"
import { dayAndMonth, historyBoundaryNotice } from "./state-copy"

/**
 * One symbol's Analyses: the ones it has, and the one being read.
 *
 * A **minimal viewer** on purpose. The inline artifact with its verdict band
 * and four fixed-order axes is the Alpha Desk surface's, and the template it
 * renders does not exist until the pipeline lands — so this shows what a
 * published Analysis actually carries today rather than a mock of what it will
 * carry.
 *
 * Opening one is what advances the user's last-seen date. Expanding the row
 * selects the newest, which is the evening's loop in one click; picking an
 * older one from the list marks that one too, and never moves the date
 * backwards.
 */
export function AnalysisPanel({
  symbol,
  initialTradingDay,
  className,
}: {
  symbol: string
  /** The session to open first — the newest Analysis the rail already knows of. */
  initialTradingDay: string | null
  className?: string
}) {
  const history = useAnalysisHistory(symbol)
  const [selected, setSelected] = useState<string | null>(initialTradingDay)
  const analysis = useAnalysis(symbol, selected)
  const markOpened = useMarkAnalysisOpened()

  // Fall back to the newest the history knows about, for a symbol whose rail
  // entry carried none — a `failed` cell whose last Analysis is older than the
  // session the rail is labelled with.
  const newest = history.data?.entries[0]?.trading_day ?? null
  useEffect(() => {
    if (selected === null && newest !== null) setSelected(newest)
  }, [selected, newest])

  const { mutate: reportOpened } = markOpened
  useEffect(() => {
    if (selected) reportOpened({ symbol, tradingDay: selected })
  }, [symbol, selected, reportOpened])

  const boundary = history.data
    ? historyBoundaryNotice(history.data.depth, history.data.older_exist)
    : null

  return (
    <div className={cn("mt-3 space-y-3 border-t border-border/60 pt-3", className)}>
      {history.isPending ? (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" /> Đang tải lịch sử Analysis…
        </p>
      ) : history.data && history.data.entries.length > 0 ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-1" role="list" aria-label={`${symbol} history`}>
            {history.data.entries.map((row) => (
              <button
                key={row.trading_day}
                type="button"
                role="listitem"
                onClick={() => setSelected(row.trading_day)}
                aria-current={row.trading_day === selected}
                className={cn(
                  "rounded border px-1.5 py-0.5 text-[11px] tabular-nums",
                  row.trading_day === selected
                    ? "border-foreground/40 bg-muted font-medium"
                    : "border-border/60 text-muted-foreground hover:bg-muted",
                )}
              >
                {dayAndMonth(row.trading_day)}
              </button>
            ))}
          </div>
          {boundary && <p className="text-[11px] text-muted-foreground">{boundary}</p>}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Chưa có Analysis nào để xem lại cho mã này.
        </p>
      )}

      {selected && <AnalysisView pending={analysis.isPending} data={analysis.data} />}
    </div>
  )
}

function AnalysisView({
  pending,
  data,
}: {
  pending: boolean
  data: AnalysisDetail | undefined
}) {
  if (pending) {
    return (
      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" /> Đang tải Analysis…
      </p>
    )
  }
  if (!data) return null

  return (
    <div className="space-y-2 rounded-md border border-border/60 bg-background/60 p-3">
      <div className="flex flex-wrap items-baseline gap-2 text-xs">
        <span className="font-semibold">{data.verdict}</span>
        <span className="text-muted-foreground tabular-nums">
          phiên {dayAndMonth(data.trading_day)}
        </span>
        {/* Several template versions are in circulation across days, so the one
            on screen has to be identifiable rather than assumed. */}
        <span className="text-muted-foreground">· template v{data.schema_version}</span>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        {Object.entries(data.payload).map(([key, value]) => (
          <div key={key} className="contents">
            <dt className="text-muted-foreground">{key}</dt>
            <dd className="min-w-0 break-words">
              {typeof value === "object" && value !== null
                ? JSON.stringify(value)
                : String(value)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
