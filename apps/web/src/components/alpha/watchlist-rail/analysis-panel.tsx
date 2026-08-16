"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"

import { AnalysisCard } from "@/components/alpha/analysis"
import { useAnalysisHistory } from "@/hooks/use-analysis"
import { cn } from "@/lib/utils"
import { dayAndMonth, historyBoundaryNotice } from "./state-copy"

/**
 * One symbol's Analyses: the ones it has, and the one being read.
 *
 * The list is this component's; the Analysis itself is drawn by the **one**
 * artifact renderer, the same one the transcript mounts. Two viewers would be
 * two answers to "what does this Analysis say", and the honesty rules — a
 * refused figure visible with its reason, a code never rendered verbatim, four
 * axes in one order — would then hold on one screen and not the other.
 *
 * What the rail adds is history: which sessions exist, and how far back the
 * browsing window reaches. Reading one is `AnalysisCard`'s, which is also what
 * advances the user's last-seen date — the rail does not report an opening of
 * its own, because two reporters is two chances to advance a badge for an
 * Analysis nobody was shown.
 *
 * Expanding the row selects the newest, which is the evening's loop in one
 * click; picking an older one from the list opens that one too, and the date
 * never moves backwards.
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

  // Fall back to the newest the history knows about, for a symbol whose rail
  // entry carried none — a `failed` cell whose last Analysis is older than the
  // session the rail is labelled with.
  const newest = history.data?.entries[0]?.trading_day ?? null
  useEffect(() => {
    if (selected === null && newest !== null) setSelected(newest)
  }, [selected, newest])

  const boundary = history.data
    ? historyBoundaryNotice(history.data.depth, history.data.older_exist)
    : null

  return (
    <div className={cn("mt-3 space-y-3 border-t border-border pt-3", className)}>
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
                  "rounded border px-1.5 py-0.5 text-micro tabular-nums",
                  row.trading_day === selected
                    ? "border-foreground/40 bg-muted font-medium"
                    : "border-border text-muted-foreground hover:bg-foreground/[0.06]",
                )}
              >
                {dayAndMonth(row.trading_day)}
              </button>
            ))}
          </div>
          {boundary && <p className="text-micro text-muted-foreground">{boundary}</p>}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Chưa có Analysis nào để xem lại cho mã này.
        </p>
      )}

      {selected && <AnalysisCard symbol={symbol} tradingDay={selected} />}
    </div>
  )
}
