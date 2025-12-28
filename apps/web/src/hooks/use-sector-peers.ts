import { useQuery } from "@tanstack/react-query"
import { fetchSectorPeers, type SectorPeersResponse } from "@/lib/api"

export function useSectorPeers(symbol: string | null, limit: number = 5) {
  return useQuery<SectorPeersResponse>({
    queryKey: ["sector-peers", symbol, limit],
    queryFn: () => fetchSectorPeers(symbol!, limit),
    enabled: !!symbol,
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}
