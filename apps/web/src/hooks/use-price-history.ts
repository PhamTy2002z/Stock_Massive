"use client"

import { useQuery } from "@tanstack/react-query"
import {
  fetchStockHistory,
  type HistoryInterval,
  type StockPricePoint,
} from "@/lib/api"
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

const isoDate = (date: Date) => date.toISOString().slice(0, 10)

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
 * Deliberately not polled: /history goes straight to the upstream provider on a
 * cache miss, and a chart that refetches on a timer is what exhausts the quota
 * everything else on the page shares.
 */
export function usePriceHistory(symbol: string, range: PriceRange) {
  return useQuery<StockPricePoint[]>({
    queryKey: queryKeys.priceHistory(symbol, range),
    queryFn: async () => {
      const { days, interval } = rangeConfig[range]
      const end = new Date()
      const start = new Date(end)
      start.setDate(start.getDate() - days)

      const points = await fetchStockHistory(symbol, isoDate(start), isoDate(end), interval)
      return range === "1D" ? lastSession(points) : points
    },
    staleTime: 4 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    refetchOnWindowFocus: false,
  })
}
