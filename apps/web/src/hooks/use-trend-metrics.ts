"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchTrendMetrics, type TrendMetricsResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

/**
 * Hook for trend metrics - requires valid symbol.
 * Consumer must check symbol validity before rendering.
 */
export function useTrendMetrics(symbol: string, periods: number = 8) {
  const { data, isFetching, refetch } =
    useSuspenseQuery<TrendMetricsResponse>({
      queryKey: queryKeys.trendMetrics(symbol, periods),
      queryFn: () => fetchTrendMetrics(symbol, periods),
      staleTime: STALE_TIME.STATIC,
    })

  // data is ALWAYS defined with useSuspenseQuery
  return {
    data,
    isFetching,
    refetch,
  }
}
