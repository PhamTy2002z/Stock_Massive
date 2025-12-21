import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import {
  fetchMarketContext,
  type MarketContextResponse,
  type MarketContextPeriod,
} from "@/lib/api"

export function useMarketContext(
  symbol: string | null,
  period: MarketContextPeriod = "3M"
) {
  return useQuery<MarketContextResponse>({
    queryKey: queryKeys.marketContext(symbol || "", period),
    queryFn: () => {
      if (!symbol) throw new Error("Symbol is required")
      return fetchMarketContext(symbol, period)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
  })
}
