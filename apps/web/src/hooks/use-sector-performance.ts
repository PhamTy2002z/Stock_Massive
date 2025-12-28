"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchSectorPerformance, type SectorPerformanceResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

interface UseSectorPerformanceResult {
  data: SectorPerformanceResponse
  isFetching: boolean
  refetch: () => void
  lastUpdated: Date | null
}

export function useSectorPerformance(): UseSectorPerformanceResult {
  const { data, isFetching, refetch, dataUpdatedAt } =
    useSuspenseQuery({
      queryKey: queryKeys.sectorPerformance,
      queryFn: fetchSectorPerformance,
      staleTime: 60 * 1000,
      refetchInterval: 120 * 1000, // 2 minutes
      refetchIntervalInBackground: false,
      refetchOnWindowFocus: true,
      refetchOnMount: true,
    })

  // data is ALWAYS defined with useSuspenseQuery
  return {
    data,
    isFetching,
    refetch,
    lastUpdated: dataUpdatedAt ? new Date(dataUpdatedAt) : null,
  }
}
