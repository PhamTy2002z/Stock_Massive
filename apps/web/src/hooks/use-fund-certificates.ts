"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchFundCertificates } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useFundCertificates(fundType?: string) {
  return useQuery({
    queryKey: queryKeys.fundCertificates(fundType),
    queryFn: () => fetchFundCertificates(fundType),
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval: 5 * 60 * 1000, // Auto-refresh every 5 minutes
  })
}
