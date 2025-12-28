import { useQuery } from "@tanstack/react-query"
import { fetchForeignSnapshot } from "@/lib/api"

export function useForeignSnapshot(symbol: string) {
  return useQuery({
    queryKey: ["foreignSnapshot", symbol],
    queryFn: () => fetchForeignSnapshot(symbol),
    enabled: !!symbol,
    staleTime: 60_000, // 1 minute
    refetchInterval: 120_000, // Auto-refresh every 2 min
  })
}
