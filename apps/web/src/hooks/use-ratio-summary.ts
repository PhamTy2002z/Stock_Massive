"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchRatioSummary, type RatioSummaryResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useRatioSummary(symbol: string | null) {
  return useQuery<RatioSummaryResponse>({
    queryKey: symbol ? queryKeys.ratioSummary(symbol) : ["ratioSummary", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchRatioSummary(symbol)
    },
    enabled: !!symbol,
    staleTime: 60 * 60 * 1000, // 1 hour
    retry: 2,
  })
}
