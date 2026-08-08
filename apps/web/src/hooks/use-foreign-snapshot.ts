import { useQuery } from "@tanstack/react-query"
import { fetchForeignSnapshot } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useForeignSnapshot(symbol: string) {
  return useQuery({
    queryKey: queryKeys.foreignSnapshot(symbol),
    queryFn: () => fetchForeignSnapshot(symbol),
    enabled: !!symbol,
    staleTime: 60_000, // 1 minute
    refetchInterval: 120_000, // Auto-refresh every 2 min
  })
}
