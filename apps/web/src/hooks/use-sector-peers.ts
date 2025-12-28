"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchSectorPeers, type SectorPeersResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

/**
 * Hook for sector peers - requires valid symbol.
 * Consumer must validate symbol before rendering.
 */
export function useSectorPeers(symbol: string, limit: number = 10) {
  const { data, isFetching, refetch, dataUpdatedAt } = useSuspenseQuery<SectorPeersResponse>({
    queryKey: queryKeys.sectorPeers(symbol),
    queryFn: () => fetchSectorPeers(symbol, limit),
    staleTime: 4 * 60 * 60 * 1000, // 4 hours per VCI rate limit strategy
    gcTime: 24 * 60 * 60 * 1000, // 24 hours for off-hours cache
  })

  return {
    data,
    isFetching,
    refetch,
    dataUpdatedAt,
  }
}
