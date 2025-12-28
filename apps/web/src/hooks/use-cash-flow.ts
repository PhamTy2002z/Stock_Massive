"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchCashFlow, type PeriodType } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

/**
 * Hook for cash flow - requires valid symbol.
 * Consumer must validate symbol before rendering.
 */
export function useCashFlow(
  symbol: string,
  period: PeriodType = "quarter",
  limit: number = 4
) {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.cashFlow(symbol, period, limit),
    queryFn: () => fetchCashFlow(symbol, period, limit),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // data is ALWAYS defined with useSuspenseQuery
  return {
    data,
    isFetching,
    refetch,
  }
}
