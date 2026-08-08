"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchSectorPerformance, type SectorPerformanceResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME, REFETCH_INTERVAL } from "@/lib/query-config"

interface UseSectorPerformanceResult {
  data: SectorPerformanceResponse | undefined
  isPending: boolean
  isFetching: boolean
  isPlaceholderData: boolean
  refetch: () => void
  lastUpdated: Date | null
}

export function useSectorPerformance(): UseSectorPerformanceResult {
  const query = useQuery({
    queryKey: queryKeys.sectorPerformance,
    queryFn: fetchSectorPerformance,
    placeholderData: keepPreviousData,
    staleTime: STALE_TIME.FREQUENT,
    refetchInterval: REFETCH_INTERVAL.FREQUENT,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isPending: query.isPending,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    refetch: query.refetch,
    lastUpdated: query.dataUpdatedAt ? new Date(query.dataUpdatedAt) : null,
  }
}
