"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchSectorPerformance, type SectorPerformanceResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

interface UseSectorPerformanceResult {
  data: SectorPerformanceResponse | null
  isLoading: boolean
  isFetching: boolean
  isPlaceholderData: boolean
  error: Error | null
  refetch: () => void
  lastUpdated: Date | null
}

export function useSectorPerformance(): UseSectorPerformanceResult {
  const query = useQuery({
    queryKey: queryKeys.sectorPerformance,
    queryFn: fetchSectorPerformance,
    staleTime: 60 * 1000,
    refetchInterval: 120 * 1000, // 2 minutes
    placeholderData: keepPreviousData,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
    lastUpdated: query.dataUpdatedAt ? new Date(query.dataUpdatedAt) : null,
  }
}
