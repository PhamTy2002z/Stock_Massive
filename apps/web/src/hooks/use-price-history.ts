"use client"

import { useQuery } from "@tanstack/react-query"
import {
  fetchMarketSeries,
  fetchStockHistory,
  type HistoryInterval,
  type MarketBar,
  type SessionInterval,
  type StockPricePoint,
} from "@/lib/api"
import { recentWindow } from "@/lib/market-session"
import { queryKeys } from "@/lib/query-keys"

export type PriceRange = "1D" | "5D" | "1M" | "6M" | "1N" | "5N"

/**
 * How far back each range reaches, and at what granularity. Longer ranges step
 * up to weekly/monthly bars so a five-year view is ~60 points instead of ~1250 —
 * the chart stays readable and the provider stays under its quota.
 *
 * 1D asks for several days of 5-minute bars and keeps the last session. It used
 * to fold raw ticks instead, but the feed only returns the last ~100 matches:
 * on a quiet close that collapsed the whole day into two candles.
 */
const rangeConfig: Record<PriceRange, { days: number; interval: HistoryInterval }> = {
  "1D": { days: 5, interval: "5m" }, // 5 calendar days always covers one session
  "5D": { days: 9, interval: "1D" }, // 9 calendar days ≈ 5 trading sessions
  "1M": { days: 31, interval: "1D" },
  "6M": { days: 183, interval: "1D" },
  "1N": { days: 366, interval: "1W" },
  "5N": { days: 1827, interval: "1M" },
}

/** Whether a range is made of whole sessions, which is all the store holds. */
const isSessionInterval = (interval: HistoryInterval): interval is SessionInterval =>
  interval === "1D" || interval === "1W" || interval === "1M"

/**
 * A stored bar in the shape the chart already draws.
 *
 * The store answers with nulls where it holds nothing; a candle needs four
 * numbers, so a bar missing any of them is dropped rather than drawn at zero.
 */
function toPricePoint(bar: MarketBar): StockPricePoint | null {
  const { open_price, high_price, low_price, close_price } = bar
  if (open_price === null || high_price === null || low_price === null) return null
  if (close_price === null) return null
  return {
    time: bar.effective_at,
    open: open_price,
    high: high_price,
    low: low_price,
    close: close_price,
    volume: bar.volume ?? 0,
  }
}

/**
 * The most recent session in the series.
 *
 * A weekend or a holiday would otherwise leave "1D" empty, and the previous
 * close is what a trader means by the last day anyway.
 */
function lastSession(points: StockPricePoint[]): StockPricePoint[] {
  if (points.length === 0) return points
  const latestDate = points[points.length - 1].time.slice(0, 10)
  return points.filter((p) => p.time.startsWith(latestDate))
}

/**
 * Price history for the deep-dive chart.
 *
 * Whole-session ranges come from the store, which holds them for every symbol
 * the Collector covers — no provider call, and the same sessions the rest of
 * the page is dated by. A symbol outside the Universe has nothing stored, and
 * the store answers with nothing rather than
 * with a chart, and that falls back to the frozen provider-backed route — which
 * is also the only path for the intraday range, since the store holds one bar
 * per session and no finer.
 *
 * Deliberately not polled: the fallback reaches a Provider Source on a cache
 * miss, and a chart that refetches on a timer is what exhausts the quota
 * everything else on the page shares.
 */
export function usePriceHistory(symbol: string, range: PriceRange) {
  return useQuery<StockPricePoint[]>({
    queryKey: queryKeys.priceHistory(symbol, range),
    queryFn: async () => {
      const { days, interval } = rangeConfig[range]
      const { start, end } = recentWindow(days)

      if (isSessionInterval(interval)) {
        const stored = await fetchMarketSeries(symbol, start, end, interval)
        // Empty counts as nothing, not as an answer: a watched symbol whose
        // history has not been loaded yet would otherwise draw a blank chart
        // where the frozen route still has sessions to show.
        const drawn = stored?.points.map(toPricePoint).filter(Boolean) ?? []
        if (drawn.length > 0) return drawn as StockPricePoint[]
      }

      const points = await fetchStockHistory(symbol, start, end, interval)
      return range === "1D" ? lastSession(points) : points
    },
    staleTime: 4 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    refetchOnWindowFocus: false,
  })
}
