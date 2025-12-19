"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchSectorPerformance, type SectorPerformanceResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

interface UseSectorPerformanceResult {
  data: SectorPerformanceResponse | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
  lastUpdated: Date | null
}

export function useSectorPerformance(): UseSectorPerformanceResult {
  const query = useQuery({
    queryKey: queryKeys.sectorPerformance,
    queryFn: fetchSectorPerformance,
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 5 * 60 * 1000, // Auto-refresh every 5 minutes
  })

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
    lastUpdated: query.dataUpdatedAt ? new Date(query.dataUpdatedAt) : null,
  }
}
