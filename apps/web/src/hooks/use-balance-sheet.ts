"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchBalanceSheet, type PeriodType } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useBalanceSheet(
  symbol: string | null,
  period: PeriodType = "quarter",
  limit: number = 4
) {
  return useQuery({
    queryKey: symbol ? queryKeys.balanceSheet(symbol, period, limit) : ["balance", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchBalanceSheet(symbol, period, limit)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}
