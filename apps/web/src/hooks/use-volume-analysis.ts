"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchVolumeAnomalies, type VolumeAnomalyResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

/**
 * Hook for volume analysis - requires valid symbol.
 * Consumer must check symbol validity before rendering.
 */
export function useVolumeAnalysis(symbol: string, days: number = 20) {
  const { data, isFetching, refetch } =
    useSuspenseQuery<VolumeAnomalyResponse>({
      queryKey: queryKeys.volumeAnalysis(symbol, days),
      queryFn: () => fetchVolumeAnomalies(symbol, days),
      staleTime: 5 * 60 * 1000, // 5 minutes
    })

  // data is ALWAYS defined with useSuspenseQuery
  return {
    data,
    isFetching,
    refetch,
  }
}
