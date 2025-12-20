import { useQuery } from "@tanstack/react-query"
import { fetchVolumeAnomalies, type VolumeAnomalyResponse } from "@/lib/api"

export function useVolumeAnalysis(symbol: string | null, days: number = 20) {
  return useQuery<VolumeAnomalyResponse>({
    queryKey: ["volume-analysis", symbol, days],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol is required")
      return fetchVolumeAnomalies(symbol, days)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
  })
}
