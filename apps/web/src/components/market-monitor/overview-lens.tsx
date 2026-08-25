"use client"

import { ArrowRight } from "lucide-react"

import { useMarketOverview } from "@/hooks/use-market-monitor"
import type { MarketMonitorUrlApi } from "@/lib/market-monitor/url-state"
import { cn } from "@/lib/utils"
import { useShell } from "@/components/shell/shell-state"

import {
  BreadthBar,
  CoverageLine,
  directionClass,
  EvidencePanel,
  formatMetric,
  LensEmpty,
  LensError,
  LensLoading,
  MetricReading,
  MonitorStateNotice,
  RotationLabel,
  SectionHeading,
  signedMetric,
} from "./monitor-primitives"
import { useReportMonitorStatus } from "./monitor-status"

export function OverviewLens({ url }: { url: MarketMonitorUrlApi }) {
  const { dispatch } = useShell()
  const query = useMarketOverview({ exchange: url.state.exchange, asOf: url.state.asOf, horizon: url.state.horizon })
  useReportMonitorStatus(query.data?.meta, query.isFetching)
  if (query.isPending) return <OverviewPanel><LensLoading /></OverviewPanel>
  if (query.isError || !query.data) return <OverviewPanel><LensError retry={() => void query.refetch()} message={query.error?.message} /></OverviewPanel>
  const data = query.data
  const breadth = data.breadth
  const advancing = breadth.advancing.value
  const declining = breadth.declining.value
  const unchanged = breadth.unchanged.value
  const lead = data.leading_sectors[0]
  const lag = data.lagging_sectors[0]

  return (
    <div id="monitor-panel-overview" aria-labelledby="monitor-tab-overview" className="grid gap-[18px]" role="tabpanel" aria-label="Tổng quan thị trường">
      <MonitorStateNotice meta={data.meta} />
      <div className="grid gap-3 lg:grid-cols-12">
        <EvidencePanel className="lg:col-span-5">
          <SectionHeading detail="Xu hướng chỉ số">Hướng thị trường</SectionHeading>
          <div className="grid gap-4 sm:grid-cols-2">
            {data.indices.map((index) => (
              <div key={index.symbol} className="min-w-0">
                <p className="text-meta font-medium text-ink-4">{index.name}</p>
                <p className="mt-1 flex flex-wrap items-baseline gap-x-2 font-mono tabular-nums">
                  <span className="text-[1.3rem] font-semibold text-ink-1">{formatMetric(index.level, 2)}</span>
                  <span className={cn("text-meta", directionClass(index.change_pct.value))}>{signedMetric(index.change_pct, 2)}</span>
                </p>
                <p className="mt-2 text-micro text-ink-5">
                  MA20 {trendWord(index.above_ma20.value)} · MA50 {trendWord(index.above_ma50.value)} · MA200 {trendWord(index.above_ma200.value)}
                </p>
              </div>
            ))}
          </div>
          {data.indices.length === 0 && <LensEmpty>Chưa có chuỗi chỉ số cho phạm vi này.</LensEmpty>}
        </EvidencePanel>

        <EvidencePanel className="lg:col-span-3">
          <SectionHeading>Độ rộng</SectionHeading>
          <div className="grid grid-cols-3 gap-2 text-center">
            <SmallFigure label="Tăng" value={advancing} className="text-positive" />
            <SmallFigure label="Không đổi" value={unchanged} className="text-reference" />
            <SmallFigure label="Giảm" value={declining} className="text-negative" />
          </div>
          <div className="mt-3"><BreadthBar advancing={advancing} declining={declining} unchanged={unchanged} /></div>
          <p className="mt-2 text-meta text-ink-5">A/D {formatMetric(breadth.advance_decline_ratio)} · Trên MA50 {formatMetric(breadth.above_ma50_pct)}</p>
          <DrillDown onClick={() => url.setLens("breadth")}>Xem độ rộng</DrillDown>
        </EvidencePanel>

        <EvidencePanel className="lg:col-span-2">
          <SectionHeading>Dẫn dắt</SectionHeading>
          {lead ? <SectorSummary row={lead} horizon={url.state.horizon} /> : <p className="text-meta text-ink-6">Chưa có ngành dẫn dắt.</p>}
          {lag && <div className="mt-3 border-t border-hairline pt-3"><SectorSummary row={lag} horizon={url.state.horizon} /></div>}
          <DrillDown onClick={() => url.setLens("sectors")}>Xem các ngành</DrillDown>
        </EvidencePanel>

        <EvidencePanel className="lg:col-span-2">
          <SectionHeading>Dòng tiền & định giá</SectionHeading>
          <MetricReading label={`Khối ngoại · ${url.state.horizon} phiên`} metric={data.foreign_flow} signed />
          <div className="mt-3 grid grid-cols-2 gap-2 border-t border-hairline pt-3">
            <MetricReading label="Chủ động / ADTV" metric={data.active_flow_over_adtv} signed />
            <MetricReading label="Thanh khoản / BQ20" metric={data.liquidity} />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 border-t border-hairline pt-3">
            <MetricReading label="P/E thị trường" metric={data.valuation.market_pe} />
            <MetricReading label="Phân vị P/E" metric={data.valuation.pe_percentile} />
          </div>
          <p className="mt-2 text-micro text-ink-6">Định giá {data.valuation.coverage.evaluated}/{data.valuation.coverage.eligible} mã</p>
          <DrillDown onClick={() => url.setLens("flow")}>Xem dòng tiền</DrillDown>
        </EvidencePanel>
      </div>

      <section>
        <SectionHeading detail="Tối đa 5 mã">Bằng chứng đáng chú ý</SectionHeading>
        {data.notable_stocks.length === 0 ? (
          <LensEmpty>Không có cổ phiếu đủ bằng chứng trong phạm vi đã chọn.</LensEmpty>
        ) : (
          <div className="divide-y divide-hairline overflow-hidden rounded-card bg-surface-raised shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.07)]">
            {data.notable_stocks.slice(0, 5).map((stock) => (
              <button
                key={stock.symbol}
                type="button"
                aria-label={`Mở chi tiết ${stock.symbol} — ${stock.name}`}
                onClick={() => dispatch({ type: "select-symbol", selected: { symbol: stock.symbol, name: stock.name, exchange: stock.exchange }, open: true })}
                onKeyDown={(event) => {
                  if (event.key !== "Enter" && event.key !== " ") return
                  event.preventDefault()
                  dispatch({ type: "select-symbol", selected: { symbol: stock.symbol, name: stock.name, exchange: stock.exchange }, open: true })
                }}
                className="flex min-h-12 w-full items-center gap-3 px-3.5 py-2.5 text-left transition-colors hover:bg-foreground/[0.035] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
              >
                <span className="w-14 shrink-0 font-mono text-control font-semibold">{stock.symbol}</span>
                <span className="min-w-0 flex-1 truncate text-meta text-ink-4">{stock.name}</span>
                <span className={cn("font-mono text-meta tabular-nums", directionClass(stock.metrics.return_1d_pct?.value))}>{signedMetric(stock.metrics.return_1d_pct)}</span>
                <ArrowRight className="size-3.5 text-ink-6" aria-hidden="true" />
              </button>
            ))}
          </div>
        )}
      </section>
      <CoverageLine meta={data.meta} updating={query.isFetching} />
    </div>
  )
}

function OverviewPanel({ children }: { children: React.ReactNode }) { return <div id="monitor-panel-overview" aria-labelledby="monitor-tab-overview" role="tabpanel">{children}</div> }

function trendWord(value: boolean | null) {
  return value === null ? "—" : value ? "trên" : "dưới"
}

function SmallFigure({ label, value, className }: { label: string; value: number | null; className: string }) {
  return <div><p className={cn("font-mono text-[1.05rem] font-semibold tabular-nums", value !== null && className)}>{value?.toLocaleString("vi-VN") ?? "—"}</p><p className="mt-0.5 text-micro text-ink-6">{label}</p></div>
}

function DrillDown({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} className="mt-3 inline-flex min-h-10 items-center gap-1.5 text-meta font-medium text-ink-3 underline decoration-foreground/20 underline-offset-4 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{children}<ArrowRight className="size-3.5" aria-hidden="true" /></button>
}

function SectorSummary({ row, horizon }: { row: import("@/lib/market-monitor/api").SectorMonitorRow; horizon: 1 | 5 | 20 }) {
  const metric = row[`return_${horizon}d_pct`]
  const relative = row[`relative_strength_${horizon}d_pct`]
  return <div><p className="truncate text-control font-medium text-ink-2">{row.name}</p><p className={cn("mt-1 font-mono text-row font-semibold", directionClass(metric.value))}>{signedMetric(metric)}</p><p className="mt-1 text-micro text-ink-5">RS {signedMetric(relative)} · <RotationLabel value={row.rotation} /></p><p className="mt-1 text-micro text-ink-6">{row.coverage.evaluated}/{row.coverage.eligible} mã</p></div>
}
