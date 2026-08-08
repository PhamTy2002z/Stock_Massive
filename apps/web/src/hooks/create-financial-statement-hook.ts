"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import type { PeriodType } from "@/lib/api"
import { STALE_TIME } from "@/lib/query-config"

/**
 * Factory for financial-statement hooks (income statement, balance sheet,
 * cash flow). All three share the same (symbol, period, limit) signature,
 * query shape, and staleTime - only the query key and fetcher differ.
 *
 * Hooks require a valid symbol; consumer must validate before rendering.
 */
export function createFinancialStatementHook<TData>(
  getQueryKey: (
    symbol: string,
    period: PeriodType,
    limit: number
  ) => readonly unknown[],
  fetcher: (symbol: string, period: PeriodType, limit: number) => Promise<TData>
) {
  return function useFinancialStatement(
    symbol: string,
    period: PeriodType = "quarter",
    limit: number = 4
  ) {
    const { data, isFetching, refetch } = useSuspenseQuery({
      queryKey: getQueryKey(symbol, period, limit),
      queryFn: () => fetcher(symbol, period, limit),
      staleTime: STALE_TIME.STATIC, // 5 minutes
    })

    // data is ALWAYS defined with useSuspenseQuery
    return {
      data,
      isFetching,
      refetch,
    }
  }
}
