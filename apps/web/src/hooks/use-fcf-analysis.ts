"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchFCFAnalysis, type FCFAnalysisResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

/**
 * Hook for FCF analysis - requires valid symbol.
 * Consumer must validate symbol before rendering.
 */
export function useFCFAnalysis(symbol: string) {
  const { data, isFetching, refetch } = useSuspenseQuery<FCFAnalysisResponse>({
    queryKey: queryKeys.fcfAnalysis(symbol),
    queryFn: () => fetchFCFAnalysis(symbol),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  return {
    data,
    isFetching,
    refetch,
  }
}
