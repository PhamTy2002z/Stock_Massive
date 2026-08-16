"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { fetchPriceBoard, type PriceBoardItem } from "@/lib/api"
import { REFETCH_INTERVAL, STALE_TIME } from "@/lib/query-config"
import { queryKeys } from "@/lib/query-keys"

/**
 * The board rows for a set of symbols: ceiling, reference, floor and the match.
 *
 * The one endpoint that carries the Vietnamese board's three reference prices,
 * which no other response has — `vn30-overview` knows the last price and the
 * change, and a board drawn from it alone would be missing the columns that
 * make it a board.
 *
 * Sorted server-side by whatever was asked for, so the caller's order is the
 * order that comes back; this keeps it that way rather than re-sorting, because
 * the caller is the one that knows why it asked in that sequence.
 */
export function usePriceBoard(symbols: string[]) {
  // Sorted for the key so two callers asking for the same set share one cache
  // entry, and the request itself follows the caller's order.
  const key = [...symbols].sort()

  return useQuery<PriceBoardItem[]>({
    queryKey: queryKeys.priceBoard(key),
    queryFn: () => fetchPriceBoard(symbols),
    enabled: symbols.length > 0,
    placeholderData: keepPreviousData,
    staleTime: STALE_TIME.REALTIME,
    refetchInterval: REFETCH_INTERVAL.REALTIME,
    refetchIntervalInBackground: false,
  })
}

/** One symbol's row, by symbol, so a list can look itself up in constant time. */
export function indexBySymbol(rows: PriceBoardItem[] | undefined) {
  const map = new Map<string, PriceBoardItem>()
  for (const row of rows ?? []) map.set(row.symbol, row)
  return map
}
