"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchTrendMetrics, type TrendMetricsResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useTrendMetrics(symbol: string | null, periods: number = 8) {
  return useQuery<TrendMetricsResponse>({
    queryKey: symbol ? queryKeys.trendMetrics(symbol, periods) : ["trendMetrics", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchTrendMetrics(symbol, periods)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
  })
}
