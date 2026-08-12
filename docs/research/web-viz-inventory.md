# Research: the chart and visualization components already in `apps/web`

Resolves issue #30. Question: if the agent produces visualizations by selecting
from a registry of typed widgets (#34), what registry can be assembled from what
already exists?

Method: in-repo only. Every file under `apps/web/src/components/` that draws a
chart, a bar, a gauge or a heatmap was read, along with the pages that compose
them, `src/lib/chart-theme.ts`, `src/app/globals.css`, `tailwind.config.js` and
`src/lib/api.ts` (the response interfaces the props are typed against). Reachability
was established by grepping for each component's identifier across `src/`. Every
claim below cites `file:line`.

## TL;DR

- **One charting library, one version: Recharts `3.10.1`** — declared
  `"recharts": "^3.10.1"` (`apps/web/package.json:38`), locked at `3.10.1`
  (`apps/web/pnpm-lock.yaml:2635`). Thirteen components import it; nothing else
  charts. Everything else is hand-rolled SVG or CSS-width bars.
- **Exactly one component today accepts arbitrary series**: `Sparkline`
  (`data: number[]`, `src/components/ui/sparkline.tsx:6-19`). Every other chart is
  typed against one endpoint's response interface, and nine of them fetch their own
  data from a `symbol` prop, so they are page fragments rather than widgets.
- **The shared theme surface is two constants** — `CHART_GRID_PROPS` and
  `CHART_TOOLTIP_STYLE` (`src/lib/chart-theme.ts:4-14`) — used by 7 of the 13
  Recharts components. The other 6 inline their own colours and tooltips. There is
  no shared axis, legend, height, number-format or empty-state convention.
- **A registry cannot be assembled without a palette fix first.** The app is
  hard-forced to the light theme (`forcedTheme="light"`,
  `src/app/layout.tsx:42-46`), but eight charts still hard-code
  `hsl(0 0% 100%)` — pure white — as a *series* colour, left over from the old dark
  build. Those series are currently invisible on a white card
  (`--card: 0 0% 100%`, `src/app/globals.css:11`). The newest chart,
  `StockValuationHistory` (`src/components/dashboard/stock-valuation-history.tsx:44`),
  is the only one that gets this right and is the pattern to copy.
- **Of the four analysis axes, news has no component at all** — `grep -riE
  "news|tin tức"` over `apps/web/src/` returns zero hits. Money flow is now
  partially served: domestic order flow has a surface, and the store-backed
  `StockSnapshotPanel` (`src/components/dashboard/stock-snapshot-panel.tsx:265`)
  prints foreign buy/sell/net and foreign room as *dated figures* (`:100-103,123-124`),
  though no chart draws foreign flow over time. Technical has price + volume but no
  indicator at all (no RSI/MACD/MA/Bollinger, no candlestick). Fundamental is the
  only axis with a full chart set.

## 1. Charting library and version

| Fact | Source |
|---|---|
| `"recharts": "^3.10.1"` | `apps/web/package.json:38` |
| resolved `recharts@3.10.1`, `engines: node >=18` | `apps/web/pnpm-lock.yaml:2635-2637` |
| 13 files import from `"recharts"` | grep `recharts` over `src/` |
| No other chart/vis library in dependencies | `apps/web/package.json` dependency block (Radix, TanStack Query, date-fns, lodash-es, lucide-react, next-themes, sonner — no d3, no visx, no chart.js, no lightweight-charts) |

Recharts primitives in use: `ComposedChart`, `BarChart`, `LineChart`, `AreaChart`,
`PieChart`, `RadarChart`, `Treemap`, plus `Bar`, `Line`, `Area`, `Pie`, `Radar`,
`Cell`, `XAxis`, `YAxis`, `CartesianGrid`, `PolarGrid`, `PolarAngleAxis`,
`ReferenceLine`, `Tooltip`, `Legend`, `ResponsiveContainer`.

Three Recharts components are code-split behind `next/dynamic` with `ssr: false`
and a skeleton `loading` (`src/components/dashboard/charts-lazy.tsx:9-33`); the
`PieChart` one is not, even though it sits in the same tab group
(`src/components/dashboard/volume-spike-dashboard/chart-tabs.tsx:4,36`).

## 2. Component inventory

Props contracts are verbatim from the source. "Agent-selectable?" answers: could an
agent pick this out of a registry and hand it data it computed, without the
component reaching for the network itself?

### 2.1 Recharts components

| Component | File:line | Renders | Props contract (verbatim) | Agent-selectable? |
|---|---|---|---|---|
| `RevenueProfitChart` | `src/components/dashboard/financial-trends/revenue-profit-chart.tsx:22` | `ComposedChart`: revenue + gross-profit bars, net-profit line, one left axis, `formatBillions` ticks, h=300 | `interface RevenueProfitChartProps {`<br>`  data: TrendMetricsResponse`<br>`}` (`:18-20`) | with changes |
| `MarginTrendChart` | `.../financial-trends/margin-trend-chart.tsx:20` | `AreaChart`: gross vs net margin, two gradient fills, `%` ticks, h=300 | `interface MarginTrendChartProps {`<br>`  data: TrendMetricsResponse`<br>`}` (`:16-18`) | with changes |
| `RoeRoaChart` | `.../financial-trends/roe-roa-chart.tsx:21` | `LineChart`: ROE + ROA, `connectNulls`, `ReferenceLine y={15}` "Benchmark 15%", h=300 | `interface RoeRoaChartProps {`<br>`  data: TrendMetricsResponse`<br>`}` (`:17-19`) | with changes |
| `CashFlowChart` | `.../financial-trends/cash-flow-chart.tsx:22` | `BarChart`: CFO/CFI/CFF grouped bars, `ReferenceLine y={0}`, h=300 | `interface CashFlowChartProps {`<br>`  data: TrendMetricsResponse`<br>`}` (`:18-20`) | with changes |
| `StockValuationHistory` | `src/components/dashboard/stock-valuation-history.tsx:44` | `LineChart`: P/E and P/B over 365 sessions on **two independent y-axes** (`:83-93`), `connectNulls`, `minTickGap={48}`, dd/MM ticks, provenance line in the header (session count · source · age · "quá cũ", `:67-71`), h=240. Uses `CHART_GRID_PROPS`/`CHART_TOOLTIP_STYLE` and `--foreground`/`--muted-foreground` strokes — theme-correct | `{ symbol: string; className?: string }` (`:44-50`) | no — calls `useValuationSeries(symbol, WINDOW_DAYS)` (`:51`) |
| `HealthRadarChart` | `.../financial-health/health-radar-chart.tsx:64` | `RadarChart` over 5 named dimensions, custom angle-aware tick renderer, h=280 | `interface HealthRadarChartProps {`<br>`  dimensions: Record<string, HealthScoreDimension>`<br>`}` (`:7-9`) | with changes |
| `VolumeAnomalyChart` | `src/components/dashboard/volume-anomaly-chart.tsx:96` | `ComposedChart`: 5-min volume bars coloured per `anomaly_level` + dashed baseline line, hourly x-ticks, own colour legend below, h=400 | `interface VolumeAnomalyChartProps {`<br>`  data: VolumeTimeSlot[]`<br>`  symbol: string`<br>`  daysAnalyzed: number`<br>`  latestDate: string \| null`<br>`  className?: string`<br>`  isPlaceholderData?: boolean`<br>`}` (`:20-27`) | with changes |
| `VolumeSpikeChart` | `src/components/dashboard/volume-spike-chart.tsx:63` | horizontal `BarChart`, top-10 industries by spike count, bar colour by count intensity, h=300 | `interface VolumeSpikeChartProps {`<br>`  industries: IndustryVolumeSpikeGroup[]`<br>`  className?: string`<br>`  isPlaceholderData?: boolean`<br>`}` (`:19-23`) | with changes |
| `VolumeSpikeComposedChart` | `src/components/dashboard/volume-spike-composed-chart.tsx:78` | `ComposedChart`, top-20 stocks: spike-ratio bars (left axis, colour by anomaly level) + price-change line (right axis), h=350 | `interface VolumeSpikeComposedChartProps {`<br>`  industries: IndustryVolumeSpikeGroup[]`<br>`  className?: string`<br>`  isPlaceholderData?: boolean`<br>`}` (`:21-25`) | with changes |
| `VolumeSpikePieChart` | `src/components/dashboard/volume-spike-pie-chart.tsx:112` | donut of top-10 spike ratios, 10-colour palette, in-slice symbol labels, clickable slices + a clickable legend list that **navigates** (`router.push("/analytics/deep-dive?symbol=")`, `:135`), h=280 | `interface VolumeSpikePieChartProps {`<br>`  industries: IndustryVolumeSpikeGroup[]`<br>`  className?: string`<br>`  isPlaceholderData?: boolean`<br>`}` (`:18-22`) | with changes |
| `VolumeSpikeTreemap` | `src/components/dashboard/volume-spike-treemap.tsx:126` | two-level `Treemap` (industry → up to 8 stocks), custom cell renderer, `hidden md:block`, h=350 | `interface VolumeSpikeTreemapProps {`<br>`  industries: IndustryVolumeSpikeGroup[]`<br>`  className?: string`<br>`}` (`:9-12`) | with changes |
| `SectorHistoricalChart` (module-private) | `src/components/dashboard/sector-historical-performance.tsx:86` | horizontal diverging bar, gainers green / losers red, `ReferenceLine x={0}`, `%` ticks, h=280 | `interface ChartProps {`<br>`  data: { name: string; value: number; isGainer: boolean }[]`<br>`  isPlaceholderData?: boolean`<br>`}` (`:81-84`) | yes, once exported |
| `OrderFlowCharts` | `src/components/dashboard/advanced-tab/widgets/order-flow-charts.tsx:242` | three sections: two hand-rolled SVG radial progress rings, a 2-bar horizontal `BarChart` (h=96px), a buy/sell gradient progress bar, net-volume tile, ATO/ATC mini-cards | `interface OrderFlowChartsProps {`<br>`  data: IntradayOrderStatsResponse \| undefined`<br>`  isLoading: boolean`<br>`}` (`:27-30`) | no |

### 2.2 Hand-rolled SVG / CSS-width visualizations

| Component | File:line | Renders | Props contract (verbatim) | Agent-selectable? |
|---|---|---|---|---|
| `Sparkline` | `src/components/ui/sparkline.tsx:21` | SVG polyline + gradient area, `--chart-1`/`--chart-2`, optional non-uniform stretch with `vector-effect` | `interface SparklineProps {`<br>`  data: number[]`<br>`  width?: number`<br>`  height?: number`<br>`  strokeWidth?: number`<br>`  className?: string`<br>`  positive?: boolean`<br>`  stretch?: boolean`<br>`}` (`:6-19`) | **yes — the only genuinely generic one** |
| `StockPriceChart` | `src/components/dashboard/stock-price-chart.tsx:120` | price line + area on a fixed 800×200 viewBox, volume bars under it, 6 x-axis labels, ref-price dashed baseline + pill, 1D/5D/1M/6M/1N/5N range chips, left-to-right reveal animation | `interface StockPriceChartProps {`<br>`  symbol: string`<br>`  refPrice?: number \| null`<br>`  className?: string`<br>`}` (`:8-13`) | no — calls `usePriceHistory(symbol, range)` itself (`:122`) and owns the range state (`:121`) |
| `StockSnapshotPanel` | `src/components/dashboard/stock-snapshot-panel.tsx:265` | Four capability blocks (price & liquidity / valuation / ownership / financials) as `<dl>` figure grids, each stamped with source badge + session date + age + a "Quá cũ" warning chip (`Provenance`, `:141`); prints foreign buy/sell/net (`:100-103`) and foreign room (`:123-124`); says "Chưa thu thập" for an uncollected block (`:191`) and refuses politely for a non-Universe symbol (`:274-283`) | `{ symbol: string; className?: string }` (`:265-271`) | no — calls `useSymbolSnapshot(symbol)` (`:272`), but its `Provenance`/`CapabilityBlock` pair is the best existing template for a widget that must date its own numbers |
| `StockRangeCards` | `src/components/dashboard/stock-range-cards.tsx:104` | three "position on a track" cards: session range, 52-week range, session liquidity vs 52-week average | 10 scalar props: `price`, `openPrice`, `lowPrice`, `highPrice`, `low52Week`, `high52Week`, `volume`, `tradingValue`, `avgVolume52Week`, `className?` — all `number \| null` (`:5-17`) | with changes (props are scalars, but the card set and Vietnamese captions are fixed) |
| `StockValuationVsSector` | `src/components/dashboard/stock-valuation-vs-sector.tsx:65` | one bar per metric (P/E, P/B, P/S, ROE, ROA) against a sector-median tick on a shared per-row scale | `interface StockValuationVsSectorProps {`<br>`  symbol: string`<br>`  className?: string`<br>`}` (`:7-10`) | no — calls `useSectorPeers(symbol)` (`:66`) |
| `FCFWaterfall` | `src/components/dashboard/fcf-analysis/fcf-waterfall.tsx:19` | four proportional bars (Net Income, CFO, CapEx, FCF) scaled to the largest absolute value; not actually a waterfall | `interface FCFWaterfallProps {`<br>`  data: FCFAnalysisResponse`<br>`}` (`:6-8`) | with changes |
| `CCCIndicator` | `src/components/dashboard/fcf-analysis/ccc-indicator.tsx:10` | big CCC number with 3-tier colour + DSO/DIO/DPO tiles; returns a "not applicable (bank)" notice when `ccc === null` | `interface CCCIndicatorProps {`<br>`  ccc: number \| null`<br>`  dso: number \| null`<br>`  dio: number \| null`<br>`  dpo: number \| null`<br>`}` (`:3-8`) | with changes |
| `ScoreBreakdown` | `src/components/dashboard/financial-health/score-breakdown.tsx:28` | one labelled progress bar per health dimension, colour by 70/50 thresholds | `interface ScoreBreakdownProps {`<br>`  dimensions: Record<string, HealthScoreDimension>`<br>`}` (`:4-6`) | with changes |
| `FScoreIndicator` | `src/components/dashboard/financial-health/f-score-indicator.tsx:25` | `score/9` progress bar + 6 pass/fail checks with icons | `interface FScoreIndicatorProps {`<br>`  score: number`<br>`  details: FScoreDetails`<br>`}` (`:5-8`) | no — `FSCORE_LABELS` is keyed on `keyof FScoreDetails` (`:10-17`), so the shape is the widget |
| `StockIndexCard` | `src/components/dashboard/stock-index-card.tsx:19` | KPI tile: name, value, signed change/percent with trend icon, optional stretched sparkline | `interface StockIndexCardProps {`<br>`  symbol: string`<br>`  name: string`<br>`  value: number`<br>`  change: number`<br>`  changePercent: number`<br>`  chartData?: number[]`<br>`  className?: string`<br>`}` (`:9-17`) | **yes** — closest thing to a reusable stat tile |
| `Split` (module-private) | `src/components/dashboard/order-flow-tab-content.tsx:30` | one measure split into buy/sell halves: percentages, a two-segment flex bar, absolute values under it | `label: string`, `buy: number`, `sell: number`, `unit: (value: number) => string` (`:31-40`) | yes, once extracted — the cleanest generic primitive in the repo |
| `OwnershipBreakdown` (module-private) | `src/components/dashboard/shareholders-tab-content.tsx:61` | single stacked bar: named holders ≥1% + "Khác", with a colour-keyed legend | `{ shareholders: ShareholderItem[] }` (`:61`) | with changes (a generic stacked-share bar is in here) |
| `PremiumBadge` | `src/components/dashboard/advanced-tab/widgets/premium-badge.tsx:59` | 5-tier coloured delta chip (>30 / >10 / ±10 / −30 / <−30) | `interface PremiumBadgeProps {`<br>`  value: number \| null`<br>`  className?: string`<br>`}` (`:5-8`) | yes — but it paints with `--stock-up` / `--stock-down`, tokens that **do not exist** in `globals.css` (see §3) |
| `IntradayOrderStats` | `src/components/dashboard/advanced-tab/widgets/intraday-order-stats.tsx:34` | buy/sell progress bar + stat tiles — an earlier, unused draft of `OrderFlowCharts` | `interface IntradayOrderStatsProps {`<br>`  data: IntradayOrderStatsResponse \| undefined`<br>`  isLoading: boolean`<br>`}` (`:16-19`) | no (and unreachable, §5) |
| Login-page showcase | `src/app/(auth)/market-showcase.tsx:22` | hardcoded VN-INDEX sparkline (`:52-57`), hardcoded sector treemap (`:75-82`), hardcoded 20-session foreign-flow bar chart (`FLOW_BARS`, `:20`, drawn `:96-104`); whole `<aside>` is `aria-hidden="true"` (`:24`) | none — no props, no data source | no — fabricated numbers, decoration only |

### 2.3 Heatmap tables and KPI rows (visualization-adjacent)

| Component | File:line | Renders | Props (verbatim) | Agent-selectable? |
|---|---|---|---|---|
| `PeerMetricsTable` | `src/components/dashboard/peer-comparison/peer-metrics-table.tsx:36` | peer table with per-cell green/red heatmap vs the peer average, target row highlighted, inline legend | `interface PeerMetricsTableProps {`<br>`  peers: PeerMetrics[]`<br>`  targetSymbol: string`<br>`}` (`:6-9`) | with changes |
| `PeerComparisonTable` | `src/components/dashboard/advanced-tab/widgets/peer-comparison-table.tsx:19` | sortable peer table using `PremiumBadge` for premium columns, row click navigates | `interface PeerComparisonTableProps {`<br>`  peers: PeerMetrics[]`<br>`  targetSymbol: string`<br>`}` (`:11-14`) | with changes |
| `RatioSummaryCard` | `src/components/dashboard/advanced-tab/widgets/ratio-summary-card.tsx:37` | 8 ratios in a 2-column grid, each coloured against a hardcoded `goodRange` | `interface RatioSummaryCardProps {`<br>`  data: RatioSummaryResponse \| undefined`<br>`  isLoading: boolean`<br>`}` (`:8-11`) | no — the 8 rows and their thresholds are a literal inside the component (`:42-93`) |
| `SectorOverviewCard` | `src/components/dashboard/advanced-tab/widgets/sector-overview-card.tsx:50` | sector median tiles with "% vs median" deltas | `icbCode`, `icbName`, `peerCount`, `median: SectorMedian`, `targetPremium?: Record<string, number \| null>` (`:8-14`) | with changes |
| `SummaryCards` | `src/components/dashboard/volume-spike-dashboard/summary-cards.tsx:8` | 3 KPI cards (total spikes / avg ratio / top industry) | `totalSpikes: number`, `avgRatio: number`, `topIndustry: string` (`:12-16`) | no — three fixed slots |
| `SpikeStockTable` | `src/components/dashboard/volume-spike-dashboard/spike-stock-table.tsx:33` | sorted, paged spike table (shared by the ranking table and each industry group) | `table: SpikeTableState`, `showRank?: boolean`, `className?: string` (`:38-40`) | no |
| `VN30OverviewTable` | `src/components/dashboard/vn30-overview-table.tsx` | VN30 board, sortable by market cap / change / volume (`:16-22`) | `{ className?: string }` (`:11-13`) — fetches its own data | no |
| `FinancialStatementsTable` | `src/components/dashboard/financial-statements-table.tsx` | Top-50-by-profit table, sortable, exchange filter, row click opens `FinancialDetailSheet` (`:392`) | `{ className?: string }` (`:29-31`) | no |
| `FundCertificates` | `src/components/dashboard/fund-certificates.tsx:26` | fund NAV list | `{ className?: string }` | no |
| `StockStatsTable`, `StockCompanyInfo`, `StockDetailPanel` | `stock-stats-table.tsx:56`, `stock-company-info.tsx:29`, `stock-detail-panel.tsx:40` | scalar stat grids, all prop-driven | scalar props (`:5-25`, `:5-14`, `:5-11`) | with changes — but unreachable today (§5) |

## 3. Shared primitives — thinner than it looks

**Colour tokens.** Two token families in `src/app/globals.css`:

- The generic shadcn ramp plus `--chart-1` … `--chart-5` (`:28-32` light, `:72-76`
  dark), mapped to Tailwind `chart.1`…`chart.5` (`apps/web/tailwind.config.js:86-91`).
  **Only `Sparkline` uses them** (`src/components/ui/sparkline.tsx:57`).
- Market semantics added by the v3 design: `--positive`, `--negative`,
  `--interactive`, `--interactive-strong`, `--hairline` (`globals.css:45-49`, dark
  `:92-96`), exposed as `positive`/`negative`/`hairline`/`interactive`
  (`tailwind.config.js:48-53`). Used by the newer surfaces
  (`stock-price-chart.tsx:171-172`, `stock-range-cards.tsx:152,158`,
  `order-flow-tab-content.tsx:56-57`, `sector-performance.tsx:49`).

Everything else invents its own colours inline: `volume-spike-chart.tsx:26-31`,
`volume-spike-composed-chart.tsx:28-36`, `volume-spike-pie-chart.tsx:25-36`
(a 10-colour palette that exists nowhere else), `volume-anomaly-chart.tsx:30-35`,
`sector-historical-performance.tsx:129`, and — worst — `order-flow-charts.tsx:33-52`,
which hardcodes *surface* colours (`cardBg: "hsl(0 0% 13%)"`,
`cardBorder: "hsl(0 0% 20%)"`) so the whole widget stays dark on a light page.

Two components reference `--stock-up` / `--stock-down`
(`premium-badge.tsx:30-31,46-47`, `sector-overview-card.tsx:29,31`,
`sector-subtab.tsx:91,99`). **Neither token is defined** anywhere in
`globals.css` or `tailwind.config.js` — those tiers render with no colour.

**The light-theme regression.** `src/app/layout.tsx:42-46` sets
`forcedTheme="light"` (the comment explains why: no theme switcher exists, and
localStorage kept old installs dark). But `--card` is `0 0% 100%`
(`globals.css:11`), and these series are painted pure white:
`revenue-profit-chart.tsx:71` (the revenue bars — the largest series),
`margin-trend-chart.tsx:32-33`, `roe-roa-chart.tsx:55,57`,
`cash-flow-chart.tsx:63`, `health-radar-chart.tsx:79-80`,
`volume-anomaly-chart.tsx:33` (the "high" anomaly tier),
`fcf-waterfall.tsx:33,35` and `score-breakdown.tsx:23` (`bg-white`). Several
components also print `text-white` headings (`health-score-card.tsx:28,48`,
`trend-charts-card.tsx:27`, `fcf-analysis-card.tsx:38,48,54`,
`peer-metrics-table.tsx:68,74`). Any widget registry inherits this bug.

**Tooltips — two conventions.**

- `contentStyle={CHART_TOOLTIP_STYLE}` with a `formatter`, in the seven components
  that import `src/lib/chart-theme.ts` (`:10-14`): the four financial-trends
  charts, `health-radar-chart.tsx:85`, `stock-valuation-history.tsx:94-98` (the only
  one that also sets a `labelFormatter`), and that is it.
- A `<Card>`-based `CustomTooltip` component redefined per file:
  `volume-spike-chart.tsx:34`, `volume-spike-composed-chart.tsx:39`,
  `volume-spike-pie-chart.tsx:52`, `volume-spike-treemap.tsx:91`,
  `volume-anomaly-chart.tsx:49`, `sector-historical-performance.tsx:50`. Five of
  them additionally set `cursor={{ fill: "hsl(var(--muted) / 0.3)" }}`.
- `order-flow-charts.tsx:391-409` writes a third variant inline.

**Axes.** `CHART_GRID_PROPS` (`chart-theme.ts:4-7`) is `strokeDasharray "3 3"` +
`stroke: hsl(var(--border))`; the volume-spike family instead writes
`<CartesianGrid strokeDasharray="3 3" className="stroke-muted" />`
(`volume-spike-chart.tsx:97`). Tick styling is per-file:
`tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}`
(`revenue-profit-chart.tsx:36`) vs `tick={{ fontSize: 11 }}` +
`className="text-muted-foreground"` (`volume-spike-chart.tsx:98`) — the latter does
not actually colour SVG text. Rotated x-labels (`angle={-45} textAnchor="end"`)
appear in `volume-spike-composed-chart.tsx:114-116` and
`volume-anomaly-chart.tsx:137-139`.

**Legends.** Three approaches: Recharts `<Legend>` with a Vietnamese `formatter`
(`revenue-profit-chart.tsx:54-65`, `cash-flow-chart.tsx:55-61`), bare `<Legend />`
(`roe-roa-chart.tsx:44`), and hand-built legend rows outside the chart
(`volume-anomaly-chart.tsx:175-192`, `volume-tab-content.tsx:163-174`,
`volume-spike-pie-chart.tsx:184-210` — the last one is interactive and navigates).

**Responsive behaviour.** Every Recharts chart is
`<ResponsiveContainer width="100%" height={N}>` with a *fixed pixel* height
(280/300/350/400). `StockPriceChart` instead uses a fixed viewBox plus
`preserveAspectRatio="none"` and `vector-effect="non-scaling-stroke"`
(`stock-price-chart.tsx:183-193`) — deliberately, so a sidebar expansion re-renders
nothing (`:114-119`). Two charts hide themselves below `md`
(`volume-spike-treemap.tsx:142`, and the treemap tab trigger
`chart-tabs.tsx:23`). No chart has a mobile-specific data reduction.

**Loading states — three conventions.**

1. Exported sibling skeleton: `VolumeSpikeChartSkeleton` (`volume-spike-chart.tsx:129`),
   `VolumeAnomalyChartSkeleton` (`:203`), `StockPriceChartSkeleton`
   (`stock-price-chart.tsx:280`), `TrendChartsCardSkeleton`
   (`trend-charts-card.tsx:75`), `HealthScoreCardSkeleton` (`health-score-card.tsx:89`),
   plus a generic `ChartSkeleton({ className, height = 300 })`
   (`src/components/ui/skeletons/chart-skeleton.tsx:10`) which **no chart component
   uses** — it is only wired into route-level `loading.tsx` files
   (`src/app/loading.tsx:15`, `src/app/analytics/deep-dive/loading.tsx:9-10`,
   `src/app/analytics/volume-spikes/loading.tsx:18`).
2. An `isLoading` prop the component branches on (`order-flow-charts.tsx:252`,
   `ratio-summary-card.tsx:38`, `intraday-order-stats.tsx:35`).
3. `useSuspenseQuery` + a `<Suspense fallback>` chosen by the parent
   (`financial-detail-sheet.tsx:48-59`, `stock-detail-client.tsx:122,137`).

Plus `isPlaceholderData` as a "dim while refetching" convention
(`volume-spike-chart.tsx:112`, `market-indices.tsx:50`,
`sector-historical-performance.tsx:181-185`) and a small spinner overlay during
refetch (`sector-historical-performance.tsx:189-193`).

**Responsive heights in use:** 240 (`stock-valuation-history.tsx:74`), 280
(`health-radar-chart.tsx:72`, `sector-historical-performance.tsx:97`, and as a
`h-[280px]` wrapper around a `height="100%"` container at
`volume-spike-pie-chart.tsx:150-151`), 300 (the four financial-trends charts,
`volume-spike-chart.tsx:91`), 350 (`volume-spike-composed-chart.tsx:105`,
`volume-spike-treemap.tsx:147`), 400 (`volume-anomaly-chart.tsx:129`), plus the
96px inline bar chart at `order-flow-charts.tsx:377`. Six different heights, no
constant.

**Provenance and staleness — a real convention, and a new one.** The store-backed
surfaces attach the Provider Source and the age of the data to every figure:
`SnapshotSectionMeta { source, effective_at, observed_at, age_seconds, stale }`
(`src/lib/api.ts:852-859`), rendered as a source badge + session date + `formatDataAge`
+ a "Quá cũ" chip by `Provenance` (`stock-snapshot-panel.tsx:141-168`), and as a
header line by `StockValuationHistory` (`:67-71`). `SeriesResponse` carries the same
two fields for the newest point only (`api.ts:980-985`). This is the one shared
convention an Analysis widget genuinely must honour — an artifact that states a
verdict has to say which session it read — and it exists in exactly two components,
neither of which is in the registry-ready set.

**Empty states — the hostile part.** Six components `return null` when they have
nothing: `volume-spike-chart.tsx:81-83`, `volume-spike-composed-chart.tsx:97`,
`volume-spike-pie-chart.tsx:138-140`, `volume-spike-treemap.tsx:139`,
`stock-valuation-history.tsx:53`, `sparkline.tsx:32-34`. (The valuation-history one is
a deliberate, documented choice — the panel below it already says the symbol is not
collected, `:41-42`.) An agent that selects one of these and gets an empty series
renders *nothing at all*, with no way to tell that apart from a crash. The better
patterns exist elsewhere and should be the registry rule: a named reason inside the
frame (`sector-historical-performance.tsx:167-176` surfaces the API's own
explanation; `stock-price-chart.tsx:135-152`; `volume-tab-content.tsx:100-111`;
`stock-valuation-vs-sector.tsx:92-100`), and the app-wide
`SurfaceEmptyState({ question, description, action, notYet })`
(`src/components/shared/surface-empty-state.tsx:23`), which is what `/compare`
ships today (`src/app/compare/page.tsx:11-16`).

**Errors.** One shared boundary, `QueryErrorBoundary`
(`src/components/providers/query-error-boundary.tsx:21`), mounted once at the root
(`src/app/layout.tsx:54`). `DataErrorNotice({ error })`
(`src/components/dashboard/advanced-tab/data-error-notice.tsx:11`) exists but its only
callers are the unreachable advanced-tab subtabs
(`advanced-tab/technical-subtab.tsx:41`, `advanced-tab/order-flow-subtab.tsx:45`).

**Number formatting.** `src/lib/format.ts` exports `formatVolume`, `formatPercent`,
`formatBillions`, `formatSessionDate`, `formatDataAge` — but `formatBillions` is
duplicated locally inside `fcf-waterfall.tsx:10-17`, `formatVolume` again inside
`volume-anomaly-chart.tsx:38-46`, and market-cap formatters are re-written in
`peer-metrics-table.tsx:21-26`, `stock-profile-sidebar.tsx:20-23`,
`stock-range-cards.tsx:28-39` and `stock-detail-panel.tsx:22-38`. Charts label in
Vietnamese with the label map hardcoded inside the component
(`revenue-profit-chart.tsx:46-50`, `cash-flow-chart.tsx:30-34`,
`health-radar-chart.tsx:11-17`, `f-score-indicator.tsx:10-17`).

## 4. What the pages compose today

This is the "must not duplicate" list for an Analysis artifact.

**Stock 360 — `/analytics/deep-dive`** (`src/app/analytics/deep-dive/page.tsx:74`,
prefetches `/detail` server-side `:22-33`, renders `StockDetailClient`). The client
(`src/components/dashboard/stock-detail-client.tsx:71-154`) is a sticky ticker bar
(`StockTickerHeader` `:92-104`) + 5 tabs (`StockDetailTabs`,
`stock-detail-tabs.tsx:18-24`) + a fixed right reference column
(`StockProfileSidebar` `:151` → profile rows + a clickable sector-peer list,
`stock-profile-sidebar.tsx:121-141`):

| Tab | Composes |
|---|---|
| Tổng quan | `StockPriceChart` (`:114`), `StockRangeCards` (`:115-125`), `StockValuationVsSector` (`:127`), `StockValuationHistory` (`:130`), `StockSnapshotPanel` (`:136`) — the last two are the store-backed additions, and the comment at `:132-134` says why the dated panel goes last |
| Dòng lệnh | `OrderFlowTabContent` (`:141`) — worded verdict card + two `Split` bars + 4 stats |
| Tài chính | `FinanceTabContent` (`:143`) — income/balance/cashflow grid table, quarter/year pills, "hide unpublished rows" toggle; **no chart** |
| Cổ đông | `ShareholdersTabContent` (`:144`) — `OwnershipBreakdown` stacked bar + paged holder table |
| Khối lượng | `VolumeTabContent` (`:145`) → `VolumeAnomalyChart` + 10/20/60-session baseline chips + 3 stats |

So the Overview tab alone already answers "what is this worth, historically, and how
old is what we know" — which is a large slice of what an Analysis artifact would
otherwise re-draw.

**Financials — `/analytics/financial-statements`**
(`src/app/analytics/financial-statements/page.tsx:4`) is `FinancialStatementsTable`
plus a row-click `FinancialDetailSheet` (`financial-statements-table.tsx:392`). The
sheet (`src/components/dashboard/financial-detail-sheet.tsx:48-59`) is the **only**
route to the richest chart set in the repo:

- `HealthScoreCard` → `HealthRadarChart` + overall score + `FScoreIndicator` +
  `ScoreBreakdown` (`health-score-card.tsx:38-65`)
- `TrendChartsCard` → 4 tabs: revenue / margin / ROE-ROA / cash flow
  (`trend-charts-card.tsx:54-68`)
- `PeerComparisonCard` → `PeerMetricsTable` (`peer-comparison-card.tsx:43`)
- `FCFAnalysisCard` → `FCFWaterfall` + FCF margin/yield + `CCCIndicator`
  (`fcf-analysis-card.tsx:42-66`)

Note the overlap already in the app: peer/valuation comparison is drawn twice, once
as bars-vs-median on Stock 360 (`StockValuationVsSector`) and once as a heatmap
table in the Financials sheet (`PeerMetricsTable`).

**Market Map — `/`** (`src/app/page.tsx:52-61`): `MarketIndices` (grid of
`StockIndexCard`, `market-indices.tsx:73-84`), `VN30OverviewTable`,
`SectorPerformanceSection` (top-5 up / top-5 down, `sector-performance.tsx:105`),
`FundCertificates`.

**Trends & Signals — `/analytics/volume-spikes`**
(`src/app/analytics/volume-spikes/page.tsx:18`): `VolumeSpikeDashboard`
(`volume-spike-dashboard/dashboard.tsx:29`) = Top50/All tabs + threshold/exchange
filters + `SummaryCards` + `SpikeChartTabs` (the four spike charts, `:222`) +
`TopVolatilityTable` (`:227`) + expandable per-industry groups (`:245-250`).

**Compare — `/compare`**: `SurfaceEmptyState` only, not built
(`src/app/compare/page.tsx:11-16`). **Workspaces — `/workspaces`**: same pattern.
Sidebar order: Market Map, Stock 360, Financials, Compare, Trends & Signals,
Workspaces (`src/components/layout/app-sidebar.tsx:33-42`).

## 5. Unreachable components (an important part of the "registry" answer)

These are exported but never mounted by any route, so they are free to be
re-purposed or deleted — and they are also the ones that reference undefined
tokens:

- `AdvancedTab` (`advanced-tab/index.tsx:55`) and its three subtabs
  (`order-flow-subtab.tsx:14`, `technical-subtab.tsx:13`, `sector-subtab.tsx:14`),
  plus `AdvancedSection` (`advanced-section.tsx:62`). Only referenced from
  `src/components/dashboard/index.ts:49-50`. Everything they render —
  `OrderFlowCharts`, `RatioSummaryCard`, `SectorOverviewCard`,
  `PeerComparisonTable`, `PremiumBadge` — is therefore dead in production.
- `SectorHistoricalPerformance` (`sector-historical-performance.tsx:198`) —
  exported at `index.ts:56`, mounted nowhere. Its private `SectorHistoricalChart`
  is the most registry-ready chart in the repo (§6).
- `IntradayOrderStats` (`intraday-order-stats.tsx:34`), `StockDetailPanel`
  (`stock-detail-panel.tsx:40`), `StockStatsTable` (`stock-stats-table.tsx:56`),
  `StockCompanyInfo` (`stock-company-info.tsx:29`) — exported, unused.
- `ChartSkeleton` (`ui/skeletons/chart-skeleton.tsx:10`) — the one generic chart
  skeleton, used by nothing.

Note also that "technical analysis" in the dead `AdvancedTab` is a misnomer: the
Technical subtab renders only `RatioSummaryCard` (P/E, P/B, ROE…,
`technical-subtab.tsx:43`) — valuation ratios, not technical indicators.

## 6. Verdict: what registry can be assembled

**Genuinely generic today (2):** `Sparkline` (`sparkline.tsx:6-19`) and
`StockIndexCard` (`stock-index-card.tsx:9-17`). Both take scalars/`number[]`.

**One rename away (1):** `SectorHistoricalChart`
(`sector-historical-performance.tsx:81-84`) already takes
`{ name, value, isGainer }[]` — a categorical diverging bar over an arbitrary
series. Export it, rename `isGainer` to a neutral `sign`/`tone`, and it is a widget.

**Generic-shaped, blocked by a response-typed prop (10).** The four
financial-trends charts, `HealthRadarChart`, `FCFWaterfall`, `ScoreBreakdown`,
`VolumeSpikeChart`, `VolumeSpikeComposedChart`, `VolumeSpikeTreemap`,
`VolumeSpikePieChart`, `VolumeAnomalyChart`. Each one's first act is to *flatten its
domain object into exactly the series a generic chart would take*:

- `data.periods.map((period, i) => ({ period, revenue: data.revenue[i], … }))`
  (`revenue-profit-chart.tsx:23-28`; identically `margin-trend-chart.tsx:21-25`,
  `roe-roa-chart.tsx:22-26`, `cash-flow-chart.tsx:23-28`)
- `Object.entries(dimensions).map(([key, dim]) => ({ dimension, score, fullMark }))`
  (`health-radar-chart.tsx:65-69`)
- `industries.flatMap(g => g.stocks).sort(…).slice(0, 20).map(…)`
  (`volume-spike-composed-chart.tsx:84-95`; same shape at
  `volume-spike-chart.tsx:68-77`, `volume-spike-pie-chart.tsx:120-132`,
  `volume-spike-treemap.tsx:127-137`)

So the work to make them agent-selectable is mechanical and identical in each case:

1. **Split each file at the mapping line.** Above it (domain object → series) becomes
   an adapter the *caller* owns; below it becomes `Chart({ categories, series })`.
   Nothing about the drawing needs to change.
2. **Lift the labels out.** Vietnamese label maps are literals inside the components
   (`revenue-profit-chart.tsx:46-50`, `cash-flow-chart.tsx:30-34`,
   `health-radar-chart.tsx:11-17`). A series must carry its own `label`, otherwise
   an agent charting anything else gets `revenue`/`cfo` as legend text.
3. **Lift the top-N and sort out.** `slice(0, 10)` / `slice(0, 20)` / `slice(0, 8)`
   are policy, not rendering (`volume-spike-chart.tsx:76`,
   `volume-spike-composed-chart.tsx:88`, `volume-spike-treemap.tsx:131`). The agent
   decides how many bars it wants.
4. **Replace `return null` with a stated empty state** (§3) — otherwise the registry
   has a silent-failure mode.
5. **Fix the palette before anything else** (§3): replace hardcoded `hsl(0 0% 100%)`
   series colours and `text-white` with `--chart-1…5` / `--positive` / `--negative`,
   define or delete `--stock-up` / `--stock-down`, and either re-theme or delete
   `order-flow-charts.tsx`'s hardcoded dark surfaces.
6. **Pick one tooltip and one axis convention** — `chart-theme.ts` is the obvious
   home, and it currently holds two constants used by half the charts.

**Not reusable as widgets, by construction (13):** `StockPriceChart`,
`StockValuationVsSector`, `StockValuationHistory`, `StockSnapshotPanel`,
`SectorHistoricalPerformance`, `MarketIndices`, `HealthScoreCard`,
`TrendChartsCard`, `PeerComparisonCard`, `FCFAnalysisCard`, and the tab bodies
`OrderFlowTabContent` / `VolumeTabContent` / `ShareholdersTabContent`. All of them
take `symbol` (or nothing) and call a hook themselves — `usePriceHistory`
(`stock-price-chart.tsx:122`), `useSectorPeers`
(`stock-valuation-vs-sector.tsx:66`, `peer-comparison-card.tsx:28`),
`useValuationSeries` (`stock-valuation-history.tsx:51`), `useSymbolSnapshot`
(`stock-snapshot-panel.tsx:272`), `useHealthScore` (`health-score-card.tsx:20`),
`useTrendMetrics` (`trend-charts-card.tsx:19`), `useFCFAnalysis`
(`fcf-analysis-card.tsx:29`), `useIntradayOrderStats`
(`order-flow-tab-content.tsx:90`), `useVolumeAnalysis`
(`volume-tab-content.tsx:96`). An agent cannot hand these its own computed numbers;
they will re-fetch from `apps/api` and draw whatever the endpoint says. They are
Stock 360's surfaces, and per #16 the Analysis artifact should **deep-link to them
rather than re-render them**. Their inner leaf charts (`HealthRadarChart`,
`FCFWaterfall`, the four trend charts, `PeerMetricsTable`) are the reusable part —
which is exactly why the registry should be built from the leaves, not the cards.

`StockValuationHistory` is worth singling out: it is the newest chart, it is
theme-correct, it uses both shared theme constants, and its dual-independent-axis
handling (`:83-93`, with the reason stated at `:39-40`) is exactly the kind of
decision a generic "two series on different scales" widget needs. Split at its
`data.points.map` (`:55-59`) and it becomes the best line-chart primitive in the repo.

Three further constraints a registry design has to absorb:

- **`VolumeSpikePieChart` navigates.** It calls `useRouter().push()` on slice and
  legend click (`volume-spike-pie-chart.tsx:117,134-136`). A widget inside a chat
  transcript needs that as an injected `onSelect`, not a hardcoded route.
- **Three components are `React.memo` with a `lodash-es` `isEqual` comparator**
  (`volume-spike-chart.tsx:124-127`, `volume-spike-composed-chart.tsx:174-177`,
  `volume-anomaly-chart.tsx:196-200`) — deep-comparing every series on every render.
  Fine for one chart per page; a transcript that accumulates dozens of widgets makes
  this a real cost.
- **A widget that shows stored data must carry its age.** Both store-backed
  surfaces treat provenance as part of the rendering, not as a caption
  (`api.ts:852-859`, `stock-snapshot-panel.tsx:141-168`,
  `stock-valuation-history.tsx:67-71`). A registry entry should take
  `{ source, effectiveAt, ageSeconds, stale }` alongside its series, or the artifact
  will state verdicts over numbers of unknown vintage.

## 7. Gaps against the four analysis axes

| Axis | Components today | Verdict |
|---|---|---|
| **Technical** | `StockPriceChart` (price line + volume bars, 6 ranges, `stock-price-chart.tsx:120`), `StockRangeCards` (session and 52-week position, `:104`), `VolumeAnomalyChart` (`:96`), the four volume-spike charts | **Partial.** Price and volume only. Zero indicators: grep for `rsi`, `macd`, `bollinger`, `sma`, `ema`, `candlestick` across `src/` returns **no hits at all**. No candlestick/OHLC chart exists even though the data is now in hand: `MarketBar` carries `open/high/low/close/volume` (`api.ts:959-966`) and
`StockPricePoint` the same (`api.ts:801-808`), `usePriceHistory` prefers the store for whole-session ranges (`use-price-history.ts:93-100`) and `toPricePoint` deliberately drops a bar missing any of the four prices (`:45-57`) — yet only `close` and `volume` are drawn (`stock-price-chart.tsx:154,166,257`), with `open` used solely to colour a volume bar (`:261`). A candlestick widget needs a renderer, not a feed. No overlay/subplot pattern anywhere, and the "Technical" subtab is actually valuation ratios (§5). |
| **Fundamental** | `HealthRadarChart`, `FScoreIndicator`, `ScoreBreakdown`, `RevenueProfitChart`, `MarginTrendChart`, `RoeRoaChart`, `CashFlowChart`, `FCFWaterfall`, `CCCIndicator`, `PeerMetricsTable`, `StockValuationVsSector`, `StockValuationHistory`, `FinanceTabContent`, `RatioSummaryCard` | **Strongest, but split in two.** The chart-rich half is reachable only through a row-click sheet on the Financials page (§4); the half on Stock 360 is bars-and-tables plus the one valuation time series. `FinanceTabContent` — the newest financial surface — has no chart at all. |
| **Money flow / foreign** | Order flow: `OrderFlowTabContent` (`:89`), `OrderFlowCharts` (dead, `:242`), `IntradayOrderStats` (dead, `:34`). Ownership: `OwnershipBreakdown` (`shareholders-tab-content.tsx:61`). Foreign: figures inside `StockSnapshotPanel` (`:100-103,123-124`). | **Numbers yes, chart no.** Domestic buy/sell order flow has a full surface. Foreign flow now exists as *dated figures* — foreign buy/sell value, net value, and remaining/total foreign room — served from the store with source and age (`api.ts:879-883,900-901`; rendered `stock-snapshot-panel.tsx:100-103,123-124`). Nothing plots them, and nothing shows them over time. The only foreign-flow *visual* in the app is still the login page's hardcoded 20-bar chart over the literal `FLOW_BARS = [16, 26, 9, -14, …]` (`market-showcase.tsx:20,88-104`), inside an `aria-hidden` decorative aside (`:24`). This partially supersedes #19: the adapters are no longer fully unwired, but no chart consumes them. |
| **News** | **None.** | **Zero components.** `grep -riE "news\|tin tức"` over all of `apps/web/src/` returns no hits. There is no article list, no headline card, no source attribution, no sentiment badge, no timeline. #17 cleared the sources and #19 found the API side is dead code; the web side is not started either. Every news element of an Analysis artifact is greenfield. |

Secondary gaps worth naming for #34: no correlation/scatter chart, no
distribution/histogram, no candlestick, no foreign-flow time series, and no
annotated-price-zone chart (the Analysis gives "direct price-zone recommendations"
per #16 — the nearest existing primitive is the single dashed ref-price line plus its
edge pill at `stock-price-chart.tsx:195-203,230-237`, which is one horizontal line, not
a band). There is no gauge or verdict badge either, except the worded verdict card at
`order-flow-tab-content.tsx:134-174` — the best existing template for how an Analysis
should state a conclusion in a sentence before drawing anything.

## 8. Method note

Read on branch `research/web-viz-inventory`, cut from `develop` at `4b1e5d7`
(the merge of `feat/store-backed-series`). Two of the components above —
`StockValuationHistory` and `StockSnapshotPanel`, plus the hooks
`use-valuation-series.ts` and `use-symbol-snapshot.ts` — arrived with that merge and
are the newest visualization code in the repo, which is why they are also the only
ones that get theming and provenance right. Line numbers will drift; the identifiers
and the argument will not.
