import type {
  MonitorExchange,
  StockPreset,
  StockSort,
  SortDirection,
} from "./url-state"

export type MonitorState =
  | "complete"
  | "partial"
  | "stale"
  | "disconnected"
  | "unavailable"

export interface MonitorCoverage {
  eligible: number
  evaluated: number
  missing: number
  state: MonitorState
}

export interface MonitorSource {
  source: string
  effective_at: string
  observed_at: string
  freshness_seconds: number
  stale: boolean
}

export interface MonitorMeta {
  exchange: MonitorExchange
  as_of: string
  generated_at: string
  state: MonitorState
  coverage: MonitorCoverage
  realtime_coverage: MonitorCoverage | null
  sources: MonitorSource[]
  issues: string[]
  method_versions: Record<string, string>
}

export interface MetricValue {
  value: number | null
  unit: string
  as_of: string
  method: string
  issues: string[]
}

export interface BreadthSummary {
  advancing: MetricValue
  declining: MetricValue
  unchanged: MetricValue
  advance_decline_ratio: MetricValue
  above_ma20_pct: MetricValue
  above_ma50_pct: MetricValue
  above_ma200_pct: MetricValue
}

export interface IndexPulse {
  symbol: string
  name: string
  level: MetricValue
  change: MetricValue
  change_pct: MetricValue
  above_ma20: EvidenceFlag
  above_ma50: EvidenceFlag
  above_ma200: EvidenceFlag
}

export interface EvidenceFlag {
  value: boolean | null
  as_of: string
  method: string
  issues: string[]
}

export interface SectorMonitorRow {
  code: string
  name: string
  exchange: MonitorExchange
  return_1d_pct: MetricValue
  return_5d_pct: MetricValue
  return_20d_pct: MetricValue
  relative_strength_1d_pct: MetricValue
  relative_strength_5d_pct: MetricValue
  relative_strength_20d_pct: MetricValue
  advancing_pct: MetricValue
  liquidity_ratio: MetricValue
  rotation: string
  coverage: MonitorCoverage
}

export interface StockMonitorRow {
  symbol: string
  name: string
  exchange: MonitorExchange
  sector_code: string | null
  sector_name: string | null
  metrics: Record<string, MetricValue>
  trend: Record<string, EvidenceFlag>
  issues: string[]
}

export interface FlowMonitorRow {
  symbol: string
  exchange: MonitorExchange
  foreign_net_1d_vnd: MetricValue
  foreign_net_5d_vnd: MetricValue
  foreign_net_20d_vnd: MetricValue
  foreign_flow_over_adtv: MetricValue
  active_flow_over_adtv: MetricValue
  quadrant: string | null
}

export interface MarketOverviewResponse {
  meta: MonitorMeta
  indices: IndexPulse[]
  breadth: BreadthSummary
  liquidity: MetricValue
  foreign_flow: MetricValue
  active_flow_over_adtv: MetricValue
  valuation: {
    market_pe: MetricValue
    market_pb: MetricValue
    pe_percentile: MetricValue
    pb_percentile: MetricValue
    coverage: MonitorCoverage
  }
  leading_sectors: SectorMonitorRow[]
  lagging_sectors: SectorMonitorRow[]
  notable_stocks: StockMonitorRow[]
}

export interface MarketBreadthResponse {
  meta: MonitorMeta
  summary: BreadthSummary
  new_high_20: MetricValue
  new_low_20: MetricValue
  new_high_252: MetricValue
  new_low_252: MetricValue
  advancing_volume_share: MetricValue
  distribution: Array<{ key: string; label: string; count: number }>
  advance_decline_line: Array<{ session_date: string; value: number | null; issues: string[] }>
}

export interface MarketFlowResponse {
  meta: MonitorMeta
  foreign_net_1d_vnd: MetricValue
  foreign_net_5d_vnd: MetricValue
  foreign_net_20d_vnd: MetricValue
  active_buy_share: MetricValue
  inflows: FlowMonitorRow[]
  outflows: FlowMonitorRow[]
  reversals: FlowMonitorRow[]
}

export interface MarketSectorResponse {
  meta: MonitorMeta
  sectors: SectorMonitorRow[]
}

export interface MarketStockPageResponse {
  meta: MonitorMeta
  lens: StockPreset
  items: StockMonitorRow[]
  next_cursor: string | null
}

export interface MarketStockDetailResponse {
  meta: MonitorMeta
  stock: StockMonitorRow
  evidence: {
    valuation: { session_date: string; pe: number | null; pb: number | null; source: string } | null
    issues: string[]
  }
}

export interface MonitorScope {
  exchange: MonitorExchange
  asOf: string | null
  horizon?: 1 | 5 | 20
}

export interface StockPageInput extends MonitorScope {
  preset: StockPreset
  sector: string | null
  sort: StockSort
  direction: SortDirection
  cursor?: string | null
}

export class MarketMonitorApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = "MarketMonitorApiError"
  }
}

const MONITOR_PROXY = "/api/alpha-desk/stocks/market-monitor"

function scopeQuery(scope: MonitorScope): URLSearchParams {
  const query = new URLSearchParams({ exchange: scope.exchange, window_days: "253" })
  if (scope.asOf) query.set("as_of", scope.asOf)
  if (scope.horizon) query.set("horizon", String(scope.horizon))
  return query
}

async function monitorGet<T>(path: string, query: URLSearchParams): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${MONITOR_PROXY}/${path}?${query}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    })
  } catch (cause) {
    const error = new MarketMonitorApiError(0, "Không thể kết nối dịch vụ Market Monitor")
    ;(error as Error & { cause?: unknown }).cause = cause
    throw error
  }
  if (!response.ok) {
    let detail = `Không đọc được dữ liệu (${response.status})`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === "string" && body.detail) detail = body.detail
    } catch {
      // Keep the status-based recovery message for non-JSON responses.
    }
    throw new MarketMonitorApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

export const fetchMarketOverview = (scope: MonitorScope) =>
  monitorGet<MarketOverviewResponse>("overview", scopeQuery(scope))

export const fetchMarketBreadth = (scope: MonitorScope) =>
  monitorGet<MarketBreadthResponse>("breadth", scopeQuery(scope))

export const fetchMarketFlows = (scope: MonitorScope) =>
  monitorGet<MarketFlowResponse>("flows", scopeQuery(scope))

export const fetchMarketSectors = (scope: MonitorScope) =>
  monitorGet<MarketSectorResponse>("sectors", scopeQuery(scope))

export function fetchMarketStocks(input: StockPageInput): Promise<MarketStockPageResponse> {
  const query = scopeQuery(input)
  query.set("lens", input.preset)
  query.set("sort_by", input.sort)
  query.set("direction", input.direction)
  query.set("limit", "25")
  if (input.sector) query.set("sector_code", input.sector)
  if (input.cursor) query.set("cursor", input.cursor)
  return monitorGet("stocks", query)
}

export function fetchMarketStockDetail(symbol: string, scope: MonitorScope) {
  return monitorGet<MarketStockDetailResponse>(
    `stocks/${encodeURIComponent(symbol)}`,
    scopeQuery(scope),
  )
}
