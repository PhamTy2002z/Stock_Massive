"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchVolumeAnomalies, type VolumeAnomalyResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

/**
 * Hook for volume analysis - requires valid symbol.
 * Consumer must check symbol validity before rendering.
 */
export function useVolumeAnalysis(symbol: string, days: number = 20) {
  const { data, isFetching, refetch } =
    useSuspenseQuery<VolumeAnomalyResponse>({
      queryKey: queryKeys.volumeAnalysis(symbol, days),
      queryFn: () => fetchVolumeAnomalies(symbol, days),
      staleTime: STALE_TIME.STATIC,
    })

  // data is ALWAYS defined with useSuspenseQuery
  return {
    data,
    isFetching,
    refetch,
  }
}
