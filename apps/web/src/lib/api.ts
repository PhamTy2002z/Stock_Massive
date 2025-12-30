// Server-side uses Docker internal network, client uses public URL
const getApiBaseUrl = () => {
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

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  })

  if (!response.ok) {
    throw new ApiError(response.status, `API error: ${response.statusText}`)
  }

  return response.json()
}

export async function fetchPriceBoard(symbols: string[]): Promise<PriceBoardItem[]> {
  const symbolsParam = symbols.join(",")
  return fetchApi<PriceBoardItem[]>(`/stocks/price-board?symbols=${encodeURIComponent(symbolsParam)}`)
}

export async function fetchMarketIndices(): Promise<MarketIndex[]> {
  const data = await fetchApi<{ symbol: string; name: string; value: number; change: number; change_pct: number }[]>(
    "/stocks/market-indices"
  )

  return data.map((item) => ({
    symbol: item.symbol,
    name: item.name,
    value: item.value,
    change: item.change,
    changePercent: item.change_pct,
  }))
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
  trading_value: number | null

  // Market Cap & Shares
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

// Advanced Tab Types - Price Depth
export interface PriceLevel {
  price: number
  volume: number
}

export interface PriceDepthResponse {
  symbol: string
  bid_1: PriceLevel
  bid_2: PriceLevel | null
  bid_3: PriceLevel | null
  ask_1: PriceLevel
  ask_2: PriceLevel | null
  ask_3: PriceLevel | null
  total_bid_volume: number
  total_ask_volume: number
  spread: number
  spread_percent: number
  timestamp: string
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

// Advanced Tab Types - Trading Stats
export interface TradingStatsResponse {
  total_volume: number | null
  avg_volume: number | null
  total_value: number | null
  avg_value: number | null
  high_price: number | null
  low_price: number | null
}

// Advanced Tab Types - Order Stats
export interface OrderStatsItem {
  date: string
  buy_orders: number
  sell_orders: number
  buy_volume: number
  sell_volume: number
  avg_buy_order?: number
  avg_sell_order?: number
}

// Advanced Tab Types - Foreign Trading
export interface ForeignTradingItem {
  date: string
  buy_volume: number
  sell_volume: number
  net_volume: number
  buy_value: number
  sell_value: number
  net_value: number
}

// Advanced Tab Types - Prop Trading
export interface PropTradingItem {
  date: string
  buy_volume: number
  sell_volume: number
  net_volume: number
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

function formatDateParam(date: Date): string {
  return date.toISOString().split("T")[0]
}

function getDateRange(days: number): { start: string; end: string } {
  const end = new Date()
  const start = new Date(Date.now() - days * 24 * 60 * 60 * 1000)
  return { start: formatDateParam(start), end: formatDateParam(end) }
}

export async function fetchOrderStats(symbol: string, days: number = 30): Promise<OrderStatsItem[]> {
  const { start, end } = getDateRange(days)
  const response = await fetchApi<{ symbol: string; items: OrderStatsItem[] }>(
    `/stocks/${encodeURIComponent(symbol)}/order-stats?start=${start}&end=${end}`
  )
  return response.items ?? []
}

export async function fetchPriceDepth(symbol: string): Promise<PriceDepthResponse> {
  return fetchApi<PriceDepthResponse>(`/stocks/${encodeURIComponent(symbol)}/price-depth`)
}

export async function fetchRatioSummary(symbol: string): Promise<RatioSummaryResponse> {
  return fetchApi<RatioSummaryResponse>(`/stocks/${encodeURIComponent(symbol)}/ratio-summary`)
}

export async function fetchTradingStats(symbol: string): Promise<TradingStatsResponse> {
  return fetchApi<TradingStatsResponse>(`/stocks/${encodeURIComponent(symbol)}/trading-stats`)
}

export async function fetchForeignTrading(symbol: string, days: number = 30): Promise<ForeignTradingItem[]> {
  const { start, end } = getDateRange(days)
  const response = await fetchApi<{ symbol: string; items: ForeignTradingItem[] }>(
    `/stocks/${encodeURIComponent(symbol)}/foreign-trading?start=${start}&end=${end}`
  )
  return response.items ?? []
}

export async function fetchPropTrading(symbol: string, days: number = 30): Promise<PropTradingItem[]> {
  const { start, end } = getDateRange(days)
  const response = await fetchApi<{ symbol: string; items: PropTradingItem[] }>(
    `/stocks/${encodeURIComponent(symbol)}/prop-trading?start=${start}&end=${end}`
  )
  return response.items ?? []
}

// === Intraday Order Stats Types (Phase 3 - Real-time current-day) ===

export interface IntradayOrderStatsResponse {
  symbol: string
  date: string
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

// === Foreign Snapshot Types (Phase 3 - Snapshot data) ===

export interface ForeignSnapshotResponse {
  symbol: string
  foreign_volume: number
  foreign_room: number
  ownership_ratio: number | null
  total_volume: number
  avg_volume_2w: number | null
  foreign_pct_of_volume: number | null
  last_updated: string
}

export async function fetchForeignSnapshot(symbol: string): Promise<ForeignSnapshotResponse> {
  return fetchApi<ForeignSnapshotResponse>(`/stocks/${encodeURIComponent(symbol)}/foreign-snapshot`)
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
  market_cap: number | null
  premium_pe: number | null
  premium_pb: number | null
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

