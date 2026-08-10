import {
  ApiUnavailableError,
  connectionStatus,
  isRetryableStatus,
} from "./connection-status"

// Server-side uses Docker internal network, client uses public URL
export const getApiBaseUrl = () => {
  // Server-side: use internal Docker network URL if available
  if (typeof window === "undefined") {
    return process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"
  }
  // Client-side: use public URL
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"
}

const API_BASE_URL = getApiBaseUrl()

export interface PriceBoardItem {
  symbol: string
  // Names vnstock 4.x uses. `last_price` / `total_vol` / `total_val` below are
  // kept as aliases of these, derived server-side, so older callers still work.
  match_price: number | null
  highest: number | null
  lowest: number | null
  accumulated_volume: number | null
  accumulated_value: number | null
  ceiling: number | null
  floor: number | null
  ref_price: number | null
  last_price: number | null
  last_vol: number | null
  total_vol: number | null
  total_val: number | null
  change: number | null
  change_pct: number | null
}

export interface MarketIndex {
  symbol: string
  name: string
  value: number
  change: number
  changePercent: number
}

export const MARKET_INDEX_SYMBOLS = ["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = "ApiError"
  }
}

/**
 * One request, with the difference between "wrong" and "not yet" preserved.
 *
 * A refused request and an unreachable API used to arrive at the UI as the
 * same thrown value, so a container restarting for two seconds surfaced as
 * `TypeError: Failed to fetch` in the user's face. Silence now reports itself
 * to `connectionStatus`, which the page veils on, and any answer at all —
 * including a 404 — is proof the API is back.
 */
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  let response: Response
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    })
  } catch (cause) {
    // fetch only rejects when the request never completed: no server, no
    // network, request aborted. There is no status to read.
    connectionStatus.reportWaiting()
    throw new ApiUnavailableError(undefined, undefined, { cause })
  }

  if (isRetryableStatus(response.status)) {
    connectionStatus.reportWaiting()
    throw new ApiUnavailableError(await readErrorDetail(response), response.status)
  }

  connectionStatus.reportReady()

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response))
  }

  return response.json()
}

/**
 * The API explains itself in `detail` — "this period has not been computed
 * yet", "the provider does not support this". Falling back to statusText threw
 * that away and showed the user a bare "Service Unavailable".
 */
async function readErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body?.detail === "string" && body.detail) return body.detail
  } catch {
    // Non-JSON error body; fall through to the status line.
  }
  return `API error: ${response.statusText || response.status}`
}

export async function fetchPriceBoard(symbols: string[]): Promise<PriceBoardItem[]> {
  const symbolsParam = symbols.join(",")
  return fetchApi<PriceBoardItem[]>(`/stocks/price-board?symbols=${encodeURIComponent(symbolsParam)}`)
}

export interface MarketIndexRaw {
  symbol: string
  name: string
  value: number
  change: number
  change_pct: number
}

export function mapMarketIndices(data: MarketIndexRaw[]): MarketIndex[] {
  return data.map((item) => ({
    symbol: item.symbol,
    name: item.name,
    value: item.value,
    change: item.change,
    changePercent: item.change_pct,
  }))
}

export async function fetchMarketIndices(): Promise<MarketIndex[]> {
  const data = await fetchApi<MarketIndexRaw[]>("/stocks/market-indices")
  return mapMarketIndices(data)
}

export interface StockSymbol {
  symbol: string
  organ_name: string | null
  exchange: string | null
  organ_type_code: string | null
}

export async function searchStocks(query: string, limit: number = 20): Promise<StockSymbol[]> {
  if (!query || query.trim().length < 1) {
    return []
  }
  return fetchApi<StockSymbol[]>(`/stocks/symbols/search?q=${encodeURIComponent(query)}&limit=${limit}`)
}

// Stock Detail Types
export interface StockDetail {
  // Basic Info
  symbol: string
  company_name: string | null
  exchange: string | null
  industry: string | null

  // Real-time Price Data
  price: number | null
  change: number | null
  change_pct: number | null
  ceiling: number | null
  floor: number | null
  ref_price: number | null

  // Intraday Range
  open_price: number | null
  high_price: number | null
  low_price: number | null

  // Volume & Value
  volume: number | null
  /** Million VND — every price field above is plain VND. */
  trading_value: number | null

  // Market Cap & Shares
  /** Billion VND. */
  market_cap: number | null
  outstanding_shares: number | null
  issue_share: number | null

  // 52-Week Data
  high_52_week: number | null
  low_52_week: number | null
  avg_volume_52_week: number | null

  // Financial Ratios
  eps: number | null
  pe: number | null
  pb: number | null
  beta: number | null
  dividend_yield: number | null
  roe: number | null
  roa: number | null

  // Company Details
  description: string | null
  website: string | null
  employees: number | null
  established_year: number | null

  // VN30 Ranking
  vn30_rank: number | null  // Rank by market cap within VN30 (1-30), null if not in VN30
}

export async function fetchStockDetail(symbol: string): Promise<StockDetail> {
  return fetchApi<StockDetail>(`/stocks/${encodeURIComponent(symbol)}/detail`)
}

// Income Statement Types
export interface IncomeStatementRow {
  id: string
  label: string
  values: Record<string, number | null>
  level: number
  is_header: boolean
  is_summary: boolean
}

export interface IncomeStatementResponse {
  symbol: string
  periods: string[]
  rows: IncomeStatementRow[]
  unit: string
}

export type PeriodType = "quarter" | "year"

export async function fetchIncomeStatement(
  symbol: string,
  period: PeriodType = "quarter",
  limit: number = 4
): Promise<IncomeStatementResponse> {
  return fetchApi<IncomeStatementResponse>(
    `/stocks/${encodeURIComponent(symbol)}/financials/income-statement?period=${period}&limit=${limit}`
  )
}

// Balance Sheet Types
export interface BalanceSheetRow {
  id: string
  label: string
  values: Record<string, number | null>
  level: number
  is_header: boolean
  is_summary: boolean
}

export interface BalanceSheetResponse {
  symbol: string
  periods: string[]
  rows: BalanceSheetRow[]
  unit: string
}

export async function fetchBalanceSheet(
  symbol: string,
  period: PeriodType = "quarter",
  limit: number = 4
): Promise<BalanceSheetResponse> {
  return fetchApi<BalanceSheetResponse>(
    `/stocks/${encodeURIComponent(symbol)}/financials/balance-sheet-detailed?period=${period}&limit=${limit}`
  )
}

// Cash Flow Types
export interface CashFlowRow {
  id: string
  label: string
  values: Record<string, number | null>
  level: number
  is_header: boolean
  is_summary: boolean
}

export interface CashFlowResponse {
  symbol: string
  periods: string[]
  rows: CashFlowRow[]
  unit: string
}

export async function fetchCashFlow(
  symbol: string,
  period: PeriodType = "quarter",
  limit: number = 4
): Promise<CashFlowResponse> {
  return fetchApi<CashFlowResponse>(
    `/stocks/${encodeURIComponent(symbol)}/financials/cash-flow?period=${period}&limit=${limit}`
  )
}

// Shareholders Types
export interface ShareholderItem {
  id: string
  name: string
  shares: number
  ownership_pct: number
  update_date: string | null
}

export interface ShareholdersResponse {
  symbol: string
  shareholders: ShareholderItem[]
  total_count: number
}

export async function fetchShareholders(symbol: string): Promise<ShareholdersResponse> {
  return fetchApi<ShareholdersResponse>(`/stocks/${encodeURIComponent(symbol)}/shareholders`)
}

// Officers Types
export interface OfficerItem {
  id: string
  name: string
  position: string
  position_short: string | null
  shares: number | null
  ownership_pct: number | null
  update_date: string | null
  status: string | null
}

export interface OfficersResponse {
  symbol: string
  officers: OfficerItem[]
  total_count: number
}

export type OfficerFilterType = "working" | "resigned" | "all"

export async function fetchOfficers(
  symbol: string,
  filterBy: OfficerFilterType = "working"
): Promise<OfficersResponse> {
  return fetchApi<OfficersResponse>(
    `/stocks/${encodeURIComponent(symbol)}/officers?filter_by=${filterBy}`
  )
}

// Insider Deals Types
export interface InsiderDealItem {
  announce_date: string
  action: string
  quantity: number
  price: number | null
  ratio: number | null
}

export interface InsiderDealsResponse {
  symbol: string
  deals: InsiderDealItem[]
  total_count: number
}

export async function fetchInsiderDeals(symbol: string): Promise<InsiderDealsResponse> {
  return fetchApi<InsiderDealsResponse>(`/stocks/${encodeURIComponent(symbol)}/insider-deals`)
}

// Sector Performance Types
export interface SectorPerformanceItem {
  icb_code: string
  icb_name: string
  change_pct: number
  total_market_cap: number
  stock_count: number
  top_gainers: string[]
  top_losers: string[]
}

export interface SectorPerformanceResponse {
  sectors: SectorPerformanceItem[]
  generated_at: string
  total_sectors: number
}

export async function fetchSectorPerformance(): Promise<SectorPerformanceResponse> {
  return fetchApi<SectorPerformanceResponse>("/stocks/sector-performance")
}

// Fund Certificates Types
export interface FundCertificateItem {
  symbol: string
  short_name: string
  fund_type: string | null
  nav: number | null
  price: number | null
  change_pct: number | null
}

export interface FundCertificatesResponse {
  funds: FundCertificateItem[]
  generated_at: string
  total_count: number
}

export async function fetchFundCertificates(fundType?: string): Promise<FundCertificatesResponse> {
  const params = fundType ? `?fund_type=${encodeURIComponent(fundType)}` : ""
  return fetchApi<FundCertificatesResponse>(`/stocks/fund-certificates${params}`)
}

// Volume Anomaly Types
export type VolumeAnomalyLevel = "normal" | "elevated" | "high" | "very_high"

export interface VolumeTimeSlot {
  hour: number
  minute_bucket: number
  time_label: string
  current_volume: number
  avg_volume: number
  volume_ratio: number
  anomaly_level: VolumeAnomalyLevel
  sample_count: number
}

export interface VolumeAnomalyResponse {
  symbol: string
  days_analyzed: number
  trading_session: string
  time_slots: VolumeTimeSlot[]
  generated_at: string
  latest_date: string | null
}

export async function fetchVolumeAnomalies(
  symbol: string,
  days: number = 20
): Promise<VolumeAnomalyResponse> {
  return fetchApi<VolumeAnomalyResponse>(
    `/stocks/${encodeURIComponent(symbol)}/volume-anomalies?days=${days}`
  )
}

// VN30 Overview Types
export interface VN30OverviewItem {
  symbol: string
  company_name: string
  price: number | null
  change_pct: number | null
  volume: number | null
  market_cap: number | null
}

export interface VN30OverviewResponse {
  stocks: VN30OverviewItem[]
  generated_at: string
  total_count: number
}

export async function fetchVN30Overview(): Promise<VN30OverviewResponse> {
  return fetchApi<VN30OverviewResponse>("/stocks/vn30-overview")
}

// Financial Statements Types
export interface FinancialStatementItem {
  rank: number
  symbol: string
  company_name: string | null
  exchange: string | null
  net_profit: number | null
  revenue: number | null
  profit_margin: number | null
  eps: number | null
  year: number
  quarter: number
}

export interface FinancialStatementsResponse {
  period: string
  updated_at: string | null
  total: number
  data: FinancialStatementItem[]
}

export async function fetchFinancialStatements(
  limit: number = 50,
  exchange?: string
): Promise<FinancialStatementsResponse> {
  const params = new URLSearchParams()
  params.set("limit", limit.toString())
  if (exchange) params.set("exchange", exchange)

  return fetchApi<FinancialStatementsResponse>(`/stocks/analytics/financial-statements?${params}`)
}

// Financial Statements Collection Result
export interface FinancialStatementsCollectionResult {
  success: number
  failed: number
  rate_limited: number
  total_symbols: number
  elapsed_seconds: number
  error: string | null
}

export async function triggerFinancialStatementsCollection(): Promise<FinancialStatementsCollectionResult> {
  return fetchApi<FinancialStatementsCollectionResult>("/stocks/analytics/financial-statements/collect", {
    method: "POST",
  })
}

// Volume Spike Types
export type VolumeSpikeAnomalyLevel = "normal" | "elevated" | "high" | "very_high"

export interface VolumeSpikeItem {
  symbol: string
  company_name: string | null
  exchange: string | null
  current_volume: number
  avg_volume_20d: number
  spike_ratio: number
  price_change_pct: number | null
  close_price: number | null
  anomaly_level: VolumeSpikeAnomalyLevel
  icb_code: string | null
  icb_name: string | null
}

export interface IndustryVolumeSpikeGroup {
  icb_code: string
  icb_name: string
  spike_count: number
  avg_spike_ratio: number
  stocks: VolumeSpikeItem[]
}

export interface VolumeSpikeMetadata {
  calculation_time_ms: number
  cache_hit: boolean
  symbols_processed: number
  symbols_with_spikes: number
}

export interface VolumeSpikeResponse {
  trade_date: string
  total_spikes: number
  industries: IndustryVolumeSpikeGroup[]
  metadata: VolumeSpikeMetadata
}

export interface VolumeSpikeParams {
  targetDate?: string
  minRatio?: number
  exchange?: string
  includeUpcom?: boolean
  limit?: number
  topProfitableOnly?: boolean
}

export async function fetchVolumeSpikes(
  params: VolumeSpikeParams = {}
): Promise<VolumeSpikeResponse> {
  const searchParams = new URLSearchParams()
  if (params.targetDate) searchParams.set("target_date", params.targetDate)
  if (params.minRatio) searchParams.set("min_ratio", params.minRatio.toString())
  if (params.exchange) searchParams.set("exchange", params.exchange)
  if (params.includeUpcom !== undefined) searchParams.set("include_upcom", String(params.includeUpcom))
  if (params.limit) searchParams.set("limit", params.limit.toString())
  if (params.topProfitableOnly) searchParams.set("top_profitable_only", "true")

  const queryString = searchParams.toString()
  return fetchApi<VolumeSpikeResponse>(
    `/stocks/analytics/volume-spikes${queryString ? `?${queryString}` : ""}`
  )
}

// Job Status Types
export type JobStatusType = "pending" | "running" | "completed" | "failed"

export interface JobStatus {
  jobId: string
  displayName: string
  status: JobStatusType
  progress: number
  totalItems: number
  processedItems: number
  message: string | null
  startedAt: string | null
  completedAt: string | null
  elapsedSeconds: number | null
}

// Advanced Tab Types - Ratio Summary
export interface RatioSummaryResponse {
  pe: number | null
  pb: number | null
  ps: number | null
  roe: number | null
  roa: number | null
  roic: number | null
  current_ratio: number | null
  debt_to_equity: number | null
}

export async function fetchJobsStatus(): Promise<JobStatus[]> {
  const data = await fetchApi<{
    job_id: string
    display_name: string
    status: JobStatusType
    progress: number
    total_items: number
    processed_items: number
    message: string | null
    started_at: string | null
    completed_at: string | null
    elapsed_seconds: number | null
  }[]>("/jobs/status")

  return data.map((item) => ({
    jobId: item.job_id,
    displayName: item.display_name,
    status: item.status,
    progress: item.progress,
    totalItems: item.total_items,
    processedItems: item.processed_items,
    message: item.message,
    startedAt: item.started_at,
    completedAt: item.completed_at,
    elapsedSeconds: item.elapsed_seconds,
  }))
}

// Advanced Tab API Functions

export async function fetchRatioSummary(symbol: string): Promise<RatioSummaryResponse> {
  return fetchApi<RatioSummaryResponse>(`/stocks/${encodeURIComponent(symbol)}/ratio-summary`)
}

// === Intraday Order Stats Types (Phase 3 - Real-time current-day) ===

export interface IntradayOrderStatsResponse {
  symbol: string
  date: string | null
  buy_orders: number
  sell_orders: number
  buy_volume: number
  sell_volume: number
  net_volume: number
  ato_volume: number
  atc_volume: number
  last_updated: string
}

export async function fetchIntradayOrderStats(symbol: string): Promise<IntradayOrderStatsResponse> {
  return fetchApi<IntradayOrderStatsResponse>(`/stocks/${encodeURIComponent(symbol)}/intraday-order-stats`)
}

// === Health Score Types (Phase 2 - Financial Health Scorecard) ===

export interface HealthScoreDimension {
  score: number
  metrics: Record<string, number | null>
}

export interface FScoreDetails {
  positive_roa: boolean
  positive_cfo: boolean
  roa_improving: boolean
  accrual_quality: boolean
  leverage_decreasing: boolean
  liquidity_improving: boolean
}

export interface HealthScoreResponse {
  symbol: string
  health_score: number
  dimensions: Record<string, HealthScoreDimension>
  f_score: number
  f_score_details: FScoreDetails
}

export async function fetchHealthScore(symbol: string): Promise<HealthScoreResponse> {
  return fetchApi<HealthScoreResponse>(`/stocks/${encodeURIComponent(symbol)}/health-score`)
}

// === Sector Peers Types (Phase 2 - Sector Comparison Dashboard) ===

export interface SectorMedian {
  pe: number | null
  pb: number | null
  ps: number | null
  roe: number | null
  roa: number | null
  market_cap: number | null
}

export interface PeerMetrics {
  symbol: string
  company_name: string | null
  roe: number | null
  roa: number | null
  pe: number | null
  pb: number | null
  ps: number | null
  market_cap: number | null
  premium_pe: number | null
  premium_pb: number | null
  premium_ps: number | null
  premium_roe: number | null
  premium_roa: number | null
}

export interface SectorPeersResponse {
  symbol: string
  icb_code: string
  icb_name: string
  peers: PeerMetrics[]
  sector_median: SectorMedian
  target_premium: Record<string, number | null>
}

export async function fetchSectorPeers(
  symbol: string,
  limit: number = 10
): Promise<SectorPeersResponse> {
  return fetchApi<SectorPeersResponse>(
    `/stocks/analytics/sector-peers?symbol=${encodeURIComponent(symbol)}&limit=${limit}`
  )
}

// === FCF Analysis Types (Phase 4 - FCF Waterfall) ===

export interface FCFAnalysisResponse {
  symbol: string
  period: string
  net_income: number | null
  cfo: number | null
  capex: number | null
  fcf: number | null
  fcf_margin: number | null
  ccc: number | null
  dso: number | null
  dio: number | null
  dpo: number | null
  market_cap: number | null
  fcf_yield: number | null
}

export async function fetchFCFAnalysis(symbol: string): Promise<FCFAnalysisResponse> {
  return fetchApi<FCFAnalysisResponse>(`/stocks/${encodeURIComponent(symbol)}/fcf-analysis`)
}

// === Trend Metrics Types (Phase 3 - Trend Charts) ===

export interface TrendMetricsResponse {
  symbol: string
  periods: string[]
  revenue: (number | null)[]
  net_profit: (number | null)[]
  gross_profit: (number | null)[]
  gross_margin: (number | null)[]
  net_margin: (number | null)[]
  roe: (number | null)[]
  roa: (number | null)[]
  cfo: (number | null)[]
  cfi: (number | null)[]
  cff: (number | null)[]
}

export async function fetchTrendMetrics(
  symbol: string,
  periods: number = 8
): Promise<TrendMetricsResponse> {
  return fetchApi<TrendMetricsResponse>(
    `/stocks/${encodeURIComponent(symbol)}/trend-metrics?periods=${periods}`
  )
}

// === Sector Historical Performance Types ===

export type SectorHistoricalPeriod = "1W" | "2W" | "1M"

export interface SectorHistoricalItem {
  icb_code: string
  icb_name: string
  change_pct: number
}

export interface SectorHistoricalResponse {
  period: string
  top_gainers: SectorHistoricalItem[]
  top_losers: SectorHistoricalItem[]
  generated_at: string | null
}

export async function fetchSectorHistoricalPerformance(
  period: SectorHistoricalPeriod = "1W"
): Promise<SectorHistoricalResponse> {
  return fetchApi<SectorHistoricalResponse>(
    `/stocks/analytics/sector-historical?period=${period}`
  )
}


// === Price History (Phase 5 - Deep dive price chart) ===

export interface StockPricePoint {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

/** Intervals the history endpoint accepts. Anything finer is served by /intraday. */
export type HistoryInterval = "1m" | "5m" | "15m" | "30m" | "1H" | "1D" | "1W" | "1M"

export async function fetchStockHistory(
  symbol: string,
  start: string,
  end: string,
  interval: HistoryInterval
): Promise<StockPricePoint[]> {
  const params = new URLSearchParams({ start, end, interval })
  return fetchApi<StockPricePoint[]>(
    `/stocks/${encodeURIComponent(symbol)}/history?${params.toString()}`
  )
}

export interface IntradayTick {
  time: string
  price: number
  volume: number
  accumulated_vol: number | null
  accumulated_val: number | null
  match_type: string | null
}

export async function fetchIntradayTicks(
  symbol: string,
  pageSize: number = 10000
): Promise<IntradayTick[]> {
  return fetchApi<IntradayTick[]>(
    `/stocks/${encodeURIComponent(symbol)}/intraday?page_size=${pageSize}`
  )
}


// === Snapshot serving ===
//
// The one route that answers from the store instead of from a provider. Every
// figure arrives with the Provider Source behind it and the age of the session
// it describes, because a number shown without its age invites the reader to
// assume it is current.

/** Where one part of the answer came from, and how old the data in it is. */
export interface SnapshotSectionMeta {
  source: string
  /** The session this describes, not the moment it was fetched. */
  effective_at: string
  observed_at: string
  age_seconds: number
  stale: boolean
}

export interface SnapshotSection<TData> extends SnapshotSectionMeta {
  data: TData
}

export interface MarketSnapshotData {
  price_unit: string
  last_price: number | null
  reference_price: number | null
  open_price: number | null
  high_price: number | null
  low_price: number | null
  ceiling_price: number | null
  floor_price: number | null
  change_pct: number | null
  volume: number | null
  total_value_vnd: number | null
  active_buy_volume: number | null
  active_sell_volume: number | null
  foreign_buy_volume: number | null
  foreign_sell_volume: number | null
  foreign_buy_value_vnd: number | null
  foreign_sell_value_vnd: number | null
  foreign_net_value_vnd: number | null
  market_cap_vnd: number | null
}

export interface ValuationSnapshotData {
  provider_pe: number | null
  provider_pb: number | null
}

/** Outstanding, listed and issued are different numbers; the type travels with the count. */
export interface ShareCountItem {
  share_type: string
  value: number
}

export interface ReferenceSnapshotData {
  shares: ShareCountItem[]
  current_foreign_room: number | null
  total_foreign_room: number | null
}

export interface FundamentalSnapshotData {
  period_end: string
  trailing_12_month_net_income_vnd: number | null
  parent_equity_vnd: number | null
}

/**
 * Everything the store holds for one symbol, part by part.
 *
 * A part with nothing collected yet is `null` rather than absent, which is how
 * "not collected" stays distinguishable from "not a capability".
 */
export interface SymbolSnapshot {
  symbol: string
  market: SnapshotSection<MarketSnapshotData> | null
  valuation: SnapshotSection<ValuationSnapshotData> | null
  reference: SnapshotSection<ReferenceSnapshotData> | null
  fundamental: SnapshotSection<FundamentalSnapshotData> | null
}

/**
 * What the collector holds for one symbol, or `null` when it holds nothing.
 *
 * A 404 from this route is an answer about the Universe rather than a failure:
 * the symbol is one this system has not been asked to follow, and the UI says
 * exactly that. A malformed symbol still throws — the caller validated it
 * before asking, so a 422 is a bug on this side, not a fact about the market.
 */
export async function fetchSymbolSnapshot(symbol: string): Promise<SymbolSnapshot | null> {
  return fetchWatched<SymbolSnapshot>(`/stocks/${encodeURIComponent(symbol)}/snapshot`)
}

/**
 * A store-backed request whose 404 means "this symbol is not watched".
 *
 * Every route that reads the store refuses an untracked symbol the same way, so
 * reading that refusal belongs in one place. Other statuses still throw: a 422
 * is a malformed symbol, which the caller validated before asking.
 */
async function fetchWatched<T>(endpoint: string): Promise<T | null> {
  try {
    return await fetchApi<T>(endpoint)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}


/** One session in a stored series, with the Provider Source that answered for it. */
export interface SeriesPoint {
  effective_at: string
  source: string
}

export interface MarketBar extends SeriesPoint {
  open_price: number | null
  high_price: number | null
  low_price: number | null
  close_price: number | null
  volume: number | null
  total_value_vnd: number | null
}

export interface ValuationPoint extends SeriesPoint {
  provider_pe: number | null
  provider_pb: number | null
}

/**
 * A stretch of sessions from the store.
 *
 * `age_seconds` and `stale` describe the newest session only — the rest of a
 * series is old by definition — and are null/false for a window the store holds
 * nothing in.
 */
export interface SeriesResponse<TPoint extends SeriesPoint> {
  symbol: string
  age_seconds: number | null
  stale: boolean
  points: TPoint[]
}

export interface MarketSeries extends SeriesResponse<MarketBar> {
  interval: string
}

export type ValuationSeries = SeriesResponse<ValuationPoint>

/** Intervals the stored series can be asked for. Anything finer is a session's inside. */
export type SessionInterval = "1D" | "1W" | "1M"

function seriesQuery(start: string, end: string, extra?: Record<string, string>) {
  return new URLSearchParams({ start, end, ...extra }).toString()
}

/**
 * Sessions for a watched symbol, or `null` when the symbol is not watched.
 *
 * The 404 is the Universe answering, not a failure — the caller falls back to
 * the frozen provider-backed route for symbols this system does not collect.
 */
export async function fetchMarketSeries(
  symbol: string,
  start: string,
  end: string,
  interval: SessionInterval
): Promise<MarketSeries | null> {
  const query = seriesQuery(start, end, { interval })
  return fetchWatched<MarketSeries>(
    `/stocks/${encodeURIComponent(symbol)}/series/market?${query}`
  )
}

/** P/E and P/B session by session, or `null` for a symbol outside the Universe. */
export async function fetchValuationSeries(
  symbol: string,
  start: string,
  end: string
): Promise<ValuationSeries | null> {
  return fetchWatched<ValuationSeries>(
    `/stocks/${encodeURIComponent(symbol)}/series/valuation?${seriesQuery(start, end)}`
  )
}
