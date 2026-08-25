"use client"

import { useCallback, useEffect, useState } from "react"

const MONITOR_URL_CHANGE_EVENT = "market-monitor-url-change"

export const MONITOR_LENSES = ["overview", "breadth", "flow", "sectors", "stocks"] as const
export const MONITOR_EXCHANGES = ["ALL", "HOSE", "HNX"] as const
export const MONITOR_HORIZONS = [1, 5, 20] as const
export const STOCK_PRESETS = ["overview", "trend", "flow", "valuation"] as const
export const STOCK_SORTS = [
  "symbol",
  "return_1d_pct",
  "return_5d_pct",
  "return_20d_pct",
  "liquidity_ratio",
  "foreign_net_20d_vnd",
  "foreign_flow_over_adtv",
] as const

export type MonitorLens = (typeof MONITOR_LENSES)[number]
export type MonitorExchange = (typeof MONITOR_EXCHANGES)[number]
export type MonitorHorizon = (typeof MONITOR_HORIZONS)[number]
export type StockPreset = (typeof STOCK_PRESETS)[number]
export type StockSort = (typeof STOCK_SORTS)[number]
export type SortDirection = "asc" | "desc"

export interface MarketMonitorUrlState {
  lens: MonitorLens
  exchange: MonitorExchange
  horizon: MonitorHorizon
  asOf: string | null
  sector: string | null
  preset: StockPreset
  sort: StockSort
  direction: SortDirection
}

export const DEFAULT_MONITOR_STATE: MarketMonitorUrlState = {
  lens: "overview",
  exchange: "ALL",
  horizon: 20,
  asOf: null,
  sector: null,
  preset: "overview",
  sort: "symbol",
  direction: "asc",
}

function member<T extends readonly string[]>(values: T, value: string | null): T[number] | null {
  return value !== null && values.includes(value as T[number]) ? (value as T[number]) : null
}

function parseDate(value: string | null): string | null {
  if (value === null || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const parsed = new Date(`${value}T00:00:00Z`)
  return Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value
    ? null
    : value
}

export function parseMarketMonitorState(search: string): MarketMonitorUrlState {
  const params = new URLSearchParams(search)
  const rawHorizon = Number(params.get("horizon"))
  const horizon = MONITOR_HORIZONS.includes(rawHorizon as MonitorHorizon)
    ? (rawHorizon as MonitorHorizon)
    : DEFAULT_MONITOR_STATE.horizon
  const sector = params.get("sector")?.trim().slice(0, 8) || null
  return {
    lens: member(MONITOR_LENSES, params.get("lens")) ?? DEFAULT_MONITOR_STATE.lens,
    exchange:
      member(MONITOR_EXCHANGES, params.get("exchange")) ?? DEFAULT_MONITOR_STATE.exchange,
    horizon,
    asOf: parseDate(params.get("as_of")),
    sector,
    preset: member(STOCK_PRESETS, params.get("preset")) ?? DEFAULT_MONITOR_STATE.preset,
    sort: member(STOCK_SORTS, params.get("sort")) ?? DEFAULT_MONITOR_STATE.sort,
    direction: params.get("direction") === "desc" ? "desc" : "asc",
  }
}

export function serializeMarketMonitorState(
  state: MarketMonitorUrlState,
  currentSearch = "",
): string {
  const params = new URLSearchParams(currentSearch)
  params.set("view", "board")
  params.set("lens", state.lens)
  params.set("exchange", state.exchange)
  params.set("horizon", String(state.horizon))
  params.set("preset", state.preset)
  params.set("sort", state.sort)
  params.set("direction", state.direction)
  if (state.asOf) params.set("as_of", state.asOf)
  else params.delete("as_of")
  if (state.sector) params.set("sector", state.sector)
  else params.delete("sector")
  return params.toString()
}

export function shellViewFromSearch(search: string): "board" | null {
  return new URLSearchParams(search).get("view") === "board" ? "board" : null
}

export function writeShellViewToHistory(view: string): void {
  const url = new URL(window.location.href)
  if (view === "board") url.searchParams.set("view", "board")
  else url.searchParams.delete("view")
  window.history.pushState(null, "", `${url.pathname}${url.search}${url.hash}`)
  window.dispatchEvent(new Event(MONITOR_URL_CHANGE_EVENT))
}

export interface MarketMonitorUrlApi {
  state: MarketMonitorUrlState
  setLens: (lens: MonitorLens) => void
  push: (patch: Partial<MarketMonitorUrlState>) => void
  replace: (patch: Partial<MarketMonitorUrlState>) => void
}

export function useMarketMonitorUrlState(): MarketMonitorUrlApi {
  const [state, setState] = useState<MarketMonitorUrlState>(DEFAULT_MONITOR_STATE)

  useEffect(() => {
    const read = (): void => setState(parseMarketMonitorState(window.location.search))
    read()
    window.addEventListener("popstate", read)
    window.addEventListener(MONITOR_URL_CHANGE_EVENT, read)
    return () => {
      window.removeEventListener("popstate", read)
      window.removeEventListener(MONITOR_URL_CHANGE_EVENT, read)
    }
  }, [])

  const write = useCallback(
    (next: MarketMonitorUrlState, history: "push" | "replace"): void => {
      const query = serializeMarketMonitorState(next, window.location.search)
      const target = `${window.location.pathname}?${query}${window.location.hash}`
      window.history[history === "push" ? "pushState" : "replaceState"](null, "", target)
      setState(next)
      window.dispatchEvent(new Event(MONITOR_URL_CHANGE_EVENT))
    },
    [],
  )

  const setLens = useCallback(
    (lens: MonitorLens): void => write({ ...state, lens }, "push"),
    [state, write],
  )
  const push = useCallback(
    (patch: Partial<MarketMonitorUrlState>): void => write({ ...state, ...patch }, "push"),
    [state, write],
  )
  const replace = useCallback(
    (patch: Partial<MarketMonitorUrlState>): void => write({ ...state, ...patch }, "replace"),
    [state, write],
  )
  return { state, setLens, push, replace }
}

const scrollPositions = new Map<string, number>()

export function monitorScrollKey(state: MarketMonitorUrlState): string {
  return [
    state.lens,
    state.exchange,
    state.horizon,
    state.asOf ?? "latest",
    state.sector ?? "all-sectors",
    state.preset,
    state.sort,
    state.direction,
  ].join(":")
}

export function rememberMonitorScroll(state: MarketMonitorUrlState, position: number): void {
  scrollPositions.set(monitorScrollKey(state), Math.max(0, position))
}

export function recalledMonitorScroll(state: MarketMonitorUrlState): number {
  return scrollPositions.get(monitorScrollKey(state)) ?? 0
}
