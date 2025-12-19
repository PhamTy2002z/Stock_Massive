"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchCashFlow, type PeriodType } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useCashFlow(
  symbol: string | null,
  period: PeriodType = "quarter",
  limit: number = 4
) {
  return useQuery({
    queryKey: symbol ? queryKeys.cashFlow(symbol, period, limit) : ["cashFlow", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchCashFlow(symbol, period, limit)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}
