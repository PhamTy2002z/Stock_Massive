"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchVolumeAnomalies, type VolumeAnomalyResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useVolumeAnalysis(symbol: string | null, days: number = 20) {
  const query = useQuery<VolumeAnomalyResponse>({
    queryKey: symbol ? queryKeys.volumeAnalysis(symbol, days) : ["volume-analysis", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol is required")
      return fetchVolumeAnomalies(symbol, days)
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
