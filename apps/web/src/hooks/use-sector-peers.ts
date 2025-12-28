"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchSectorPeers, type SectorPeersResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useSectorPeers(symbol: string | null, limit: number = 10) {
  return useQuery<SectorPeersResponse>({
    queryKey: symbol ? queryKeys.sectorPeers(symbol) : ["sectorPeers", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchSectorPeers(symbol, limit)
    },
    enabled: !!symbol,
    staleTime: 4 * 60 * 60 * 1000, // 4 hours per VCI rate limit strategy
    gcTime: 24 * 60 * 60 * 1000, // 24 hours for off-hours cache
    retry: 2,
  })
}
