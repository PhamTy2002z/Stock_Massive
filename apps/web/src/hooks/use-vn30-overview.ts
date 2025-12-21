"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchVN30Overview } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useVN30Overview() {
  return useQuery({
    queryKey: queryKeys.vn30Overview,
    queryFn: fetchVN30Overview,
    staleTime: 60 * 1000,        // 1 minute
    refetchInterval: 60 * 1000,  // Auto-refresh every 1 minute
    refetchIntervalInBackground: false,  // Prevent unnecessary API calls when tab inactive
  })
}
