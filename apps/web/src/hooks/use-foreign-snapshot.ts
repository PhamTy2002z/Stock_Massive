import { useQuery } from "@tanstack/react-query"
import { fetchForeignSnapshot } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME, REFETCH_INTERVAL } from "@/lib/query-config"

export function useForeignSnapshot(symbol: string) {
  return useQuery({
    queryKey: queryKeys.foreignSnapshot(symbol),
    queryFn: () => fetchForeignSnapshot(symbol),
    enabled: !!symbol,
    staleTime: STALE_TIME.FREQUENT,
    refetchInterval: REFETCH_INTERVAL.FREQUENT,
  })
}
