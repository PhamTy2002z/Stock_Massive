"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchIncomeStatement, type PeriodType } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

/**
 * Hook for income statement - requires valid symbol.
 * Consumer must validate symbol before rendering.
 */
export function useIncomeStatement(
  symbol: string,
  period: PeriodType = "quarter",
  limit: number = 4
) {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.incomeStatement(symbol, period, limit),
    queryFn: () => fetchIncomeStatement(symbol, period, limit),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // data is ALWAYS defined with useSuspenseQuery
  return {
    data,
    isFetching,
    refetch,
  }
}
