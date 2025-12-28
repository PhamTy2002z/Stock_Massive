"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchHealthScore, type HealthScoreResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

/**
 * Hook for health score - requires valid symbol.
 * Consumer must check symbol validity before rendering.
 */
export function useHealthScore(symbol: string) {
  const { data, isFetching, isRefetching, refetch, dataUpdatedAt } =
    useSuspenseQuery<HealthScoreResponse>({
      queryKey: queryKeys.healthScore(symbol),
      queryFn: () => fetchHealthScore(symbol),
      staleTime: 5 * 60 * 1000, // 5 minutes
    })

  // data is ALWAYS defined with useSuspenseQuery
  return {
    data,
    isFetching,
    isRefetching,
    refetch,
    dataUpdatedAt,
  }
}
