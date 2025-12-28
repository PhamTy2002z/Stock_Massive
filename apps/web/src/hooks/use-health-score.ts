"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchHealthScore, type HealthScoreResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useHealthScore(symbol: string | null) {
  const query = useQuery<HealthScoreResponse>({
    queryKey: symbol ? queryKeys.healthScore(symbol) : ["healthScore", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchHealthScore(symbol)
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
    isRefetching: query.isRefetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
    dataUpdatedAt: query.dataUpdatedAt,
  }
}
