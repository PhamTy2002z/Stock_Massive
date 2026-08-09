"use client"

import { useQuery } from "@tanstack/react-query"
import {
  fetchIntradayTicks,
  fetchStockHistory,
  type HistoryInterval,
  type IntradayTick,
  type StockPricePoint,
} from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export type PriceRange = "1D" | "5D" | "1M" | "6M" | "1N" | "5N"

/** Minutes per candle when folding raw ticks into the intraday series. */
const INTRADAY_BUCKET_MINUTES = 5

/**
 * Ticks arrive one per match — thousands of them, newest first. Folding them
 * into 5-minute candles gives the chart the same ~80 points the other ranges
 * have, and turns per-match volume into something a bar can show.
 */
function bucketTicks(ticks: IntradayTick[]): StockPricePoint[] {
  const buckets = new Map<string, StockPricePoint>()

  // Oldest first, so open/close land on the right end of each bucket.
  for (const tick of [...ticks].reverse()) {
    const date = new Date(tick.time)
    if (Number.isNaN(date.getTime())) continue

    date.setMinutes(Math.floor(date.getMinutes() / INTRADAY_BUCKET_MINUTES) * INTRADAY_BUCKET_MINUTES, 0, 0)
    const key = date.toISOString()
    const existing = buckets.get(key)

    if (!existing) {
      buckets.set(key, {
        time: key,
        open: tick.price,
        high: tick.price,
        low: tick.price,
        close: tick.price,
        volume: tick.volume,
      })
      continue
    }

    existing.high = Math.max(existing.high, tick.price)
    existing.low = Math.min(existing.low, tick.price)
    existing.close = tick.price
    existing.volume += tick.volume
  }

  return [...buckets.values()]
}

/**
 * How far back each range reaches, and at what granularity. Longer ranges step
 * up to weekly/monthly bars so a five-year view is ~60 points instead of ~1250 —
 * the chart stays readable and the provider stays under its quota.
 */
const rangeConfig: Record<
  Exclude<PriceRange, "1D">,
  { days: number; interval: HistoryInterval }
> = {
  "5D": { days: 9, interval: "1D" }, // 9 calendar days ≈ 5 trading sessions
  "1M": { days: 31, interval: "1D" },
  "6M": { days: 183, interval: "1D" },
  "1N": { days: 366, interval: "1W" },
  "5N": { days: 1827, interval: "1M" },
}

const isoDate = (date: Date) => date.toISOString().slice(0, 10)

/**
 * Price history for the deep-dive chart.
 *
 * Deliberately not polled: /history goes straight to the upstream provider on a
 * cache miss, and a chart that refetches on a timer is what exhausts the quota
 * everything else on the page shares.
 */
export function usePriceHistory(symbol: string, range: PriceRange) {
  return useQuery<StockPricePoint[]>({
    queryKey: queryKeys.priceHistory(symbol, range),
    queryFn: async () => {
      if (range === "1D") {
        return bucketTicks(await fetchIntradayTicks(symbol))
      }

      const { days, interval } = rangeConfig[range]
      const end = new Date()
      const start = new Date(end)
      start.setDate(start.getDate() - days)
      return fetchStockHistory(symbol, isoDate(start), isoDate(end), interval)
    },
    staleTime: 4 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    refetchOnWindowFocus: false,
  })
}
