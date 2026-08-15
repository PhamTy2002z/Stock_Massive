"use client"

import { Loader2, RotateCw, X } from "lucide-react"

import type { AnalysisState, RailEntry } from "@/lib/alpha"
import { cn } from "@/lib/utils"
import { STATE_LABEL, dayAndMonth, failureSentence, stateSentence } from "./state-copy"

/**
 * The five states, each with its own colour, so they are told apart before they
 * are read. `unsupported` is deliberately not red: it is a fact about the
 * Universe, not a failure of anything.
 */
const STATE_TONE: Record<AnalysisState, string> = {
  ready: "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  pending: "border-border/60 bg-muted/40 text-muted-foreground",
  producing: "border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-400",
  failed: "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400",
  unsupported: "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400",
}

export interface RailEntryRowProps {
  entry: RailEntry
  /** The session the rail is labelled with, which is what a state is relative to. */
  tradingDay: string | null
  onRemove: (symbol: string) => void
  onRetry: (symbol: string, tradingDay: string) => void
  isRemoving?: boolean
  isRetrying?: boolean
}

/**
 * One symbol on the rail.
 *
 * **A `failed` cell never renders empty.** It shows the most recent Analysis
 * that does exist, the dated label naming the session that is missing, and a
 * retry. An empty cell tells the user there is nothing to see while a month of
 * history sits behind it.
 *
 * The retry disappears at the three-attempt ceiling rather than staying and
 * doing nothing — the API already says when that has been reached.
 */
export function RailEntryRow({
  entry,
  tradingDay,
  onRemove,
  onRetry,
  isRemoving,
  isRetrying,
}: RailEntryRowProps) {
  const { symbol, state, latest, failure } = entry
  const failureReason = failure ? failureSentence(failure) : null
  const canRetry = state === "failed" && tradingDay !== null && !failure?.exhausted

  return (
    <li className="rounded-lg border border-border/60 bg-card/50 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold tracking-tight">{symbol}</span>
            <span
              className={cn(
                "rounded border px-1.5 py-0.5 text-[11px] font-medium",
                STATE_TONE[state],
              )}
            >
              {STATE_LABEL[state]}
            </span>
          </div>

          <p className="text-xs text-muted-foreground">
            {stateSentence(state, tradingDay)}
          </p>

          {latest ? (
            <p className="text-xs">
              <span className="text-muted-foreground">Latest:</span>{" "}
              <span className="font-medium">{latest.verdict}</span>{" "}
              <span className="text-muted-foreground tabular-nums">
                · phiên {dayAndMonth(latest.trading_day)}
              </span>
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              Chưa có Analysis nào cho mã này.
            </p>
          )}

          {failureReason && (
            <p className="text-xs text-red-600 dark:text-red-400">{failureReason}</p>
          )}

          {failure?.exhausted && (
            <p className="text-xs text-muted-foreground">
              Đã thử {failure.attempts}/{failure.max_attempts} lượt cho phiên này; chờ
              phiên kế tiếp.
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1">
          {canRetry && (
            <button
              type="button"
              onClick={() => onRetry(symbol, tradingDay!)}
              disabled={isRetrying}
              className="inline-flex items-center gap-1 rounded-md border border-border/60 px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
              aria-label={`Retry ${symbol}`}
            >
              <RotateCw className={cn("h-3 w-3", isRetrying && "animate-spin")} />
              Retry
            </button>
          )}
          <button
            type="button"
            onClick={() => onRemove(symbol)}
            disabled={isRemoving}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
            aria-label={`Remove ${symbol}`}
          >
            {isRemoving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <X className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>
    </li>
  )
}
