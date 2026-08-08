"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchHealthScore, type HealthScoreResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

/**
 * Hook for health score - requires valid symbol.
 * Consumer must check symbol validity before rendering.
 */
export function useHealthScore(symbol: string) {
  const { data, isFetching, isRefetching, refetch, dataUpdatedAt } =
    useSuspenseQuery<HealthScoreResponse>({
      queryKey: queryKeys.healthScore(symbol),
      queryFn: () => fetchHealthScore(symbol),
      staleTime: STALE_TIME.STATIC,
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
