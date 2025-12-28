"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchHealthScore, type HealthScoreResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useHealthScore(symbol: string | null) {
  return useQuery<HealthScoreResponse>({
    queryKey: symbol ? queryKeys.healthScore(symbol) : ["healthScore", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchHealthScore(symbol)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
  })
}
