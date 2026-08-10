"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import { fetchSymbolSnapshot, type SymbolSnapshot } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

/**
 * What the collector holds for one symbol. `null` means it holds nothing.
 *
 * No refetch interval: the store changes once a session, when the collector
 * runs, so polling it every fifteen seconds would ask the same question a
 * thousand times for one new answer. The age inside the response is what tells
 * the reader whether to look again.
 */
export function useSymbolSnapshot(symbol: string) {
  return useSuspenseQuery<SymbolSnapshot | null>({
    queryKey: queryKeys.symbolSnapshot(symbol),
    queryFn: () => fetchSymbolSnapshot(symbol),
    staleTime: STALE_TIME.STATIC,
  })
}
