"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchTrendMetrics, type TrendMetricsResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useTrendMetrics(symbol: string | null, periods: number = 8) {
  const query = useQuery<TrendMetricsResponse>({
    queryKey: symbol ? queryKeys.trendMetrics(symbol, periods) : ["trendMetrics", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchTrendMetrics(symbol, periods)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
    placeholderData: keepPreviousData,
    retry: 2,
  })

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
  }
}
