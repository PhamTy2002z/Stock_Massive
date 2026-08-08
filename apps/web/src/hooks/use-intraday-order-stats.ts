import { useQuery } from "@tanstack/react-query"
import { fetchIntradayOrderStats } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME, REFETCH_INTERVAL } from "@/lib/query-config"

export function useIntradayOrderStats(symbol: string) {
  return useQuery({
    queryKey: queryKeys.intradayOrderStats(symbol),
    queryFn: () => fetchIntradayOrderStats(symbol),
    enabled: !!symbol,
    staleTime: STALE_TIME.FREQUENT, // short for real-time data
    refetchInterval: REFETCH_INTERVAL.FREQUENT,
  })
}
