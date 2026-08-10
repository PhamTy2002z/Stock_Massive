"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchValuationSeries, type ValuationSeries } from "@/lib/api"
import { recentWindow } from "@/lib/market-session"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

/**
 * P/E and P/B session by session, or `null` for a symbol outside the Universe.
 *
 * No refetch interval: the series gains one point a session, when the collector
 * runs. The age inside the response is what tells the reader whether to look
 * again, and polling would ask the same question all evening for one new point.
 */
export function useValuationSeries(symbol: string, days: number) {
  return useSuspenseQuery<ValuationSeries | null>({
    queryKey: queryKeys.valuationSeries(symbol, days),
    queryFn: () => {
      const { start, end } = recentWindow(days)
      return fetchValuationSeries(symbol, start, end)
    },
    staleTime: STALE_TIME.STATIC,
  })
}
