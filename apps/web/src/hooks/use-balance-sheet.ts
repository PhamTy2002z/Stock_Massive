"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchBalanceSheet, type PeriodType } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

/**
 * Hook for balance sheet - requires valid symbol.
 * Consumer must validate symbol before rendering.
 */
export function useBalanceSheet(
  symbol: string,
  period: PeriodType = "quarter",
  limit: number = 4
) {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.balanceSheet(symbol, period, limit),
    queryFn: () => fetchBalanceSheet(symbol, period, limit),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // data is ALWAYS defined with useSuspenseQuery
  return {
    data,
    isFetching,
    refetch,
  }
}
