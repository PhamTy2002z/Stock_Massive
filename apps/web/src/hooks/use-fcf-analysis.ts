"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchFCFAnalysis, type FCFAnalysisResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

/**
 * Hook for FCF analysis - requires valid symbol.
 * Consumer must validate symbol before rendering.
 */
export function useFCFAnalysis(symbol: string) {
  const { data, isFetching, refetch } = useSuspenseQuery<FCFAnalysisResponse>({
    queryKey: queryKeys.fcfAnalysis(symbol),
    queryFn: () => fetchFCFAnalysis(symbol),
    staleTime: STALE_TIME.STATIC,
  })

  return {
    data,
    isFetching,
    refetch,
  }
}
