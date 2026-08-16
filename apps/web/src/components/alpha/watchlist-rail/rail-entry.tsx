"use client"

import { Loader2, RotateCw, X } from "lucide-react"

import type { AnalysisState, RailEntry } from "@/lib/alpha"
import { cn } from "@/lib/utils"
import { STATE_LABEL, dayAndMonth, failureSentence, stateSentence } from "./state-copy"

/**
 * The five states as a badge — border, fill and text — so they are told apart
 * before they are read.
 *
 * The dot form of the same vocabulary lives in `state-copy.ts`, because the
 * Alpha Desk dock shows these five states too and a second palette would mean
 * one symbol reading amber there and red here. This fuller treatment has only
 * ever had one caller, and stays with it.
 */
const STATE_TONE: Record<AnalysisState, string> = {
  ready: "border-positive/40 bg-positive/10 text-positive",
  pending: "border-border bg-foreground/[0.04] text-muted-foreground",
  producing: "border-primary/40 bg-primary/10 text-primary",
  failed: "border-negative/40 bg-negative/10 text-negative",
  unsupported: "border-caution/40 bg-caution/10 text-caution",
}

export interface RailEntryRowProps {
  entry: RailEntry
  /** The session the rail is labelled with, which is what a state is relative to. */
  tradingDay: string | null
  onRemove: (symbol: string) => void
  onRetry: (symbol: string, tradingDay: string) => void
  /** Expand the symbol to read its Analyses. Expanding is what "opening" means. */
  onToggle?: (symbol: string) => void
  isOpen?: boolean
  isRemoving?: boolean
  isRetrying?: boolean
  /** The viewer, rendered by the container so this row stays presentational. */
  children?: React.ReactNode
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
  onToggle,
  isOpen,
  isRemoving,
  isRetrying,
  children,
}: RailEntryRowProps) {
  const { symbol, state, latest, failure, unread } = entry
  const failureReason = failure ? failureSentence(failure) : null
  const canRetry = state === "failed" && tradingDay !== null && !failure?.exhausted

  return (
    <li className="rounded-lg border border-border bg-card p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            {onToggle ? (
              <button
                type="button"
                onClick={() => onToggle(symbol)}
                aria-expanded={!!isOpen}
                className="font-semibold tracking-tight hover:underline"
              >
                {symbol}
              </button>
            ) : (
              <span className="font-semibold tracking-tight">{symbol}</span>
            )}
            {/* One symbol, one badge, cleared by opening that symbol's Analysis
                and nothing else. */}
            {unread && (
              <span
                aria-label={`${symbol} has an unread Analysis`}
                className="h-1.5 w-1.5 rounded-full bg-primary"
              />
            )}
            <span
              className={cn(
                "rounded border px-1.5 py-0.5 text-micro font-medium",
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

          {failureReason &&
            (state === "failed" ? (
              <p className="text-xs text-negative">{failureReason}</p>
            ) : (
              // A queued symbol that has already failed once keeps its reason.
              // Shown as the *previous* attempt's, and not in red: nothing is
              // wrong right now, it is waiting its turn.
              <p className="text-xs text-muted-foreground">
                Lượt trước: {failureReason}
              </p>
            ))}

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
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-foreground/[0.06] disabled:opacity-50"
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
            className="rounded-md p-1 text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground disabled:opacity-50"
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

      {isOpen && children}
    </li>
  )
}
