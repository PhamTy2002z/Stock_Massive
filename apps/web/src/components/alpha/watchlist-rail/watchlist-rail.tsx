"use client"

import { useState } from "react"

import { AlphaRefusalError, type WatchlistAddition } from "@/lib/alpha"
import { useRailMutations, useWatchlistRail } from "@/hooks/use-watchlist-rail"
import { cn } from "@/lib/utils"
import { AddSymbolForm } from "./add-symbol-form"
import { AnalysisPanel } from "./analysis-panel"
import { RailEntryRow } from "./rail-entry"
import { RailHeader } from "./rail-header"
import { WatchlistRailSkeleton } from "./skeleton"
import { SystemStatusLine } from "./status-line"
import { onDemandSentence } from "./state-copy"

/**
 * The Watchlist rail: this user's symbols against the dated Trading Day.
 *
 * **It never assumes a full-height column of its own.** No `h-full`, no
 * `min-h-screen`, no scroll container: it sizes to its content and lets
 * whatever mounts it decide the box. That is what lets the same component be
 * this page today and a compact persistent dock inside the Alpha Desk surface
 * later, rather than being rebuilt there.
 *
 * Mutations invalidate the rail instead of patching a cached copy, so the state
 * on screen after a change is the one the server computed — an addition can
 * seat a symbol *and* queue an Analysis, and reassembling that here would be a
 * second implementation of rules that already exist upstream.
 */
export function WatchlistRail({ className }: { className?: string }) {
  const { data, isPending, isError, error, refetch } = useWatchlistRail()
  const { add, remove, retry } = useRailMutations()
  const [addition, setAddition] = useState<WatchlistAddition | null>(null)
  // One symbol open at a time. Ten expanded artifacts is a page, not a rail —
  // and the compact dock this becomes later has room for exactly one.
  const [openSymbol, setOpenSymbol] = useState<string | null>(null)

  if (isPending) return <WatchlistRailSkeleton className={className} />

  if (isError || !data) {
    return (
      <div className={cn("rounded-lg border border-border/60 p-4 text-sm", className)}>
        <p className="text-muted-foreground">
          Chưa đọc được Watchlist:{" "}
          {error instanceof Error ? error.message : "lỗi không xác định"}.
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-2 rounded-md border border-border/60 px-2 py-1 text-xs hover:bg-muted"
        >
          Reload
        </button>
      </div>
    )
  }

  const refusal =
    add.error instanceof AlphaRefusalError
      ? add.error.message
      : add.error instanceof Error
        ? add.error.message
        : null

  return (
    <section className={cn("flex flex-col gap-3", className)} aria-label="Watchlist">
      <RailHeader
        tradingDay={data.trading_day}
        count={data.count}
        cap={data.cap}
        unreadCount={data.entries.filter((entry) => entry.unread).length}
      />

      <SystemStatusLine tradingDay={data.trading_day} />

      <AddSymbolForm
        isAdding={add.isPending}
        error={refusal}
        notice={
          addition
            ? onDemandSentence(addition.on_demand.outcome, addition.on_demand.message)
            : null
        }
        onAdd={(symbol) => {
          setAddition(null)
          add.mutate(symbol, { onSuccess: setAddition })
        }}
      />

      {data.entries.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border/60 p-4 text-center text-xs text-muted-foreground">
          Watchlist đang trống. Thêm một mã để hệ thống dựng Analysis mỗi phiên.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {data.entries.map((entry) => (
            <RailEntryRow
              key={entry.symbol}
              entry={entry}
              tradingDay={data.trading_day}
              isOpen={openSymbol === entry.symbol}
              isRemoving={remove.isPending && remove.variables === entry.symbol}
              isRetrying={retry.isPending && retry.variables?.symbol === entry.symbol}
              onToggle={(symbol) =>
                setOpenSymbol((open) => (open === symbol ? null : symbol))
              }
              onRemove={(symbol) => remove.mutate(symbol)}
              onRetry={(symbol, tradingDay) => retry.mutate({ symbol, tradingDay })}
            >
              <AnalysisPanel
                symbol={entry.symbol}
                initialTradingDay={entry.latest?.trading_day ?? null}
              />
            </RailEntryRow>
          ))}
        </ul>
      )}
    </section>
  )
}
