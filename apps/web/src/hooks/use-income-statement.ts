"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchIncomeStatement, type PeriodType } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useIncomeStatement(
  symbol: string | null,
  period: PeriodType = "quarter",
  limit: number = 4
) {
  const query = useQuery({
    queryKey: symbol ? queryKeys.incomeStatement(symbol, period, limit) : ["income", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchIncomeStatement(symbol, period, limit)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
    placeholderData: keepPreviousData,
  })

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
  }
}
