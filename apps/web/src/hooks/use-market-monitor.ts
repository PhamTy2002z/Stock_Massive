"use client"

import { useInfiniteQuery, useQuery } from "@tanstack/react-query"

import {
  fetchMarketBreadth,
  fetchMarketFlows,
  fetchMarketOverview,
  fetchMarketSectors,
  fetchMarketStockDetail,
  fetchMarketStocks,
  type MonitorScope,
  type StockPageInput,
} from "@/lib/market-monitor/api"
import { REFETCH_INTERVAL, STALE_TIME } from "@/lib/query-config"
import { queryKeys } from "@/lib/query-keys"

const liveOptions = {
  staleTime: STALE_TIME.FAST,
  refetchInterval: REFETCH_INTERVAL.FAST,
  placeholderData: <T>(previous: T | undefined) => previous,
  throwOnError: false,
} as const

export function useMarketOverview(scope: MonitorScope) {
  return useQuery({
    queryKey: queryKeys.marketMonitor.overview(scope),
    queryFn: () => fetchMarketOverview(scope),
    ...liveOptions,
  })
}

export function useMarketBreadth(scope: MonitorScope) {
  return useQuery({
    queryKey: queryKeys.marketMonitor.breadth(scope),
    queryFn: () => fetchMarketBreadth(scope),
    staleTime: STALE_TIME.FREQUENT,
    placeholderData: (previous) => previous,
    throwOnError: false,
  })
}

export function useMarketFlows(scope: MonitorScope) {
  return useQuery({
    queryKey: queryKeys.marketMonitor.flows(scope),
    queryFn: () => fetchMarketFlows(scope),
    ...liveOptions,
  })
}

export function useMarketSectors(scope: MonitorScope) {
  return useQuery({
    queryKey: queryKeys.marketMonitor.sectors(scope),
    queryFn: () => fetchMarketSectors(scope),
    staleTime: STALE_TIME.FREQUENT,
    placeholderData: (previous) => previous,
    throwOnError: false,
  })
}

export function useMarketStocks(input: StockPageInput) {
  return useInfiniteQuery({
    queryKey: queryKeys.marketMonitor.stocks(input),
    queryFn: ({ pageParam }) => fetchMarketStocks({ ...input, cursor: pageParam }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    staleTime: STALE_TIME.FREQUENT,
    throwOnError: false,
  })
}

export function useMarketStockDetail(symbol: string, scope: MonitorScope, enabled = true) {
  return useQuery({
    queryKey: queryKeys.marketMonitor.stockDetail(symbol, scope),
    queryFn: () => fetchMarketStockDetail(symbol, scope),
    enabled: enabled && symbol.length > 0,
    staleTime: STALE_TIME.FREQUENT,
    placeholderData: (previous) => previous,
    throwOnError: false,
  })
}
