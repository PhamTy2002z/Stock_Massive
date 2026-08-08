import { useQuery } from "@tanstack/react-query"
import { fetchIntradayOrderStats } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useIntradayOrderStats(symbol: string) {
  return useQuery({
    queryKey: queryKeys.intradayOrderStats(symbol),
    queryFn: () => fetchIntradayOrderStats(symbol),
    enabled: !!symbol,
    staleTime: 60_000, // 1 minute - short for real-time data
    refetchInterval: 120_000, // Auto-refresh every 2 min
  })
}
