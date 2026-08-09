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
 * Ticks arrive one per match. Folding them into 5-minute candles turns
 * per-match volume into something a bar can show.
 *
 * Sorted by timestamp rather than reversed: the feed hands them back oldest
 * first, so reversing them drew the session backwards — the axis ran from
 * 14:45 down to 14:25.
 */
const pad = (value: number) => String(value).padStart(2, "0")

/** `2026-08-07T14:25:00` — the same shape the feed uses, so it parses back. */
function localTimestamp(date: Date): string {
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:00`
  )
}

function bucketTicks(ticks: IntradayTick[]): StockPricePoint[] {
  const buckets = new Map<string, StockPricePoint>()

  const chronological = [...ticks].sort(
    (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()
  )

  // Oldest first, so open/close land on the right end of each bucket.
  for (const tick of chronological) {
    const date = new Date(tick.time)
    if (Number.isNaN(date.getTime())) continue

    date.setMinutes(Math.floor(date.getMinutes() / INTRADAY_BUCKET_MINUTES) * INTRADAY_BUCKET_MINUTES, 0, 0)
    // Kept as a local timestamp, not toISOString(): the feed sends session
    // times without a zone, and a UTC round-trip would relabel 14:25 as 07:25
    // for anyone reading the board from outside Vietnam.
    const key = localTimestamp(date)
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
