"use client"

import { useMemo } from "react"

import { useMarketBreadth } from "@/hooks/use-market-monitor"
import type { MarketMonitorUrlApi } from "@/lib/market-monitor/url-state"

import {
  BreadthBar,
  CoverageLine,
  EvidencePanel,
  LensError,
  LensLoading,
  MetricReading,
  MonitorStateNotice,
  SectionHeading,
} from "./monitor-primitives"
import { useReportMonitorStatus } from "./monitor-status"

export function BreadthLens({ url }: { url: MarketMonitorUrlApi }) {
  const query = useMarketBreadth({ exchange: url.state.exchange, asOf: url.state.asOf })
  useReportMonitorStatus(query.data?.meta, query.isFetching)
  if (query.isPending) return <BreadthPanel><LensLoading /></BreadthPanel>
  if (query.isError || !query.data) return <BreadthPanel><LensError retry={() => void query.refetch()} message={query.error?.message} /></BreadthPanel>
  const data = query.data
  const summary = data.summary
  const advancing = summary.advancing.value
  const declining = summary.declining.value
  const unchanged = summary.unchanged.value

  return (
    <div id="monitor-panel-breadth" aria-labelledby="monitor-tab-breadth" className="grid gap-[18px]" role="tabpanel" aria-label="Độ rộng thị trường">
      <MonitorStateNotice meta={data.meta} />
      <EvidencePanel>
        <SectionHeading detail={`Mẫu ${data.meta.coverage.evaluated}/${data.meta.coverage.eligible}`}>Phiên tăng và giảm</SectionHeading>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricReading label="Tăng" metric={summary.advancing} />
          <MetricReading label="Giảm" metric={summary.declining} />
          <MetricReading label="Không đổi" metric={summary.unchanged} />
          <MetricReading label="Tỷ lệ A/D" metric={summary.advance_decline_ratio} />
        </div>
        <div className="mt-4"><BreadthBar advancing={advancing} declining={declining} unchanged={unchanged} /></div>
      </EvidencePanel>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]">
        <EvidencePanel>
          <SectionHeading>Phân bố lợi suất</SectionHeading>
          <DistributionBars buckets={data.distribution} />
        </EvidencePanel>
        <EvidencePanel>
          <SectionHeading detail={`${data.advance_decline_line.length} phiên`}>Đường tích lũy A/D</SectionHeading>
          <AdvanceDeclineChart points={data.advance_decline_line} />
        </EvidencePanel>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <EvidencePanel>
          <SectionHeading>Độ rộng xu hướng</SectionHeading>
          <div className="grid grid-cols-3 gap-3">
            <MetricReading label="Trên MA20" metric={summary.above_ma20_pct} />
            <MetricReading label="Trên MA50" metric={summary.above_ma50_pct} />
            <MetricReading label="Trên MA200" metric={summary.above_ma200_pct} />
          </div>
        </EvidencePanel>
        <EvidencePanel>
          <SectionHeading>Đỉnh, đáy và khối lượng</SectionHeading>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-5">
            <MetricReading label="Đỉnh 20P" metric={data.new_high_20} />
            <MetricReading label="Đáy 20P" metric={data.new_low_20} />
            <MetricReading label="Đỉnh 252P" metric={data.new_high_252} />
            <MetricReading label="Đáy 252P" metric={data.new_low_252} />
            <MetricReading label="KL mã tăng" metric={data.advancing_volume_share} />
          </div>
        </EvidencePanel>
      </div>
      <CoverageLine meta={data.meta} updating={query.isFetching} />
    </div>
  )
}

function BreadthPanel({ children }: { children: React.ReactNode }) { return <div id="monitor-panel-breadth" aria-labelledby="monitor-tab-breadth" role="tabpanel">{children}</div> }

function DistributionBars({ buckets }: { buckets: Array<{ key: string; label: string; count: number }> }) {
  const peak = Math.max(1, ...buckets.map((bucket) => bucket.count))
  return <div className="grid gap-2.5">{buckets.map((bucket) => <div key={bucket.key} className="grid grid-cols-[86px_minmax(0,1fr)_36px] items-center gap-2 text-meta"><span className="text-ink-4">{bucket.label}</span><span className="h-2 overflow-hidden rounded-pill bg-foreground/[0.055]"><span className="block h-full rounded-pill bg-widget" style={{ width: `${(bucket.count / peak) * 100}%` }} /></span><span className="text-right font-mono tabular-nums text-ink-2">{bucket.count}</span></div>)}</div>
}

function AdvanceDeclineChart({ points }: { points: Array<{ session_date: string; value: number | null; issues: string[] }> }) {
  const paths = useMemo(() => {
    const valid = points.map((point, index) => ({ ...point, index })).filter((point): point is typeof point & { value: number } => point.value !== null)
    if (valid.length < 2) return []
    const low = Math.min(...valid.map((point) => point.value))
    const high = Math.max(...valid.map((point) => point.value))
    const span = high - low || 1
    const x = (index: number) => (index / Math.max(1, points.length - 1)) * 600
    const y = (value: number) => 170 - ((value - low) / span) * 150
    const groups: string[] = []
    let current = ""
    points.forEach((point, index) => {
      if (point.value === null) { if (current) groups.push(current); current = ""; return }
      current += `${current ? " L" : "M"}${x(index).toFixed(1)} ${y(point.value).toFixed(1)}`
    })
    if (current) groups.push(current)
    return groups
  }, [points])
  if (paths.length === 0) return <p className="flex h-44 items-center justify-center text-meta text-ink-6">Chưa đủ điểm liên tục để dựng đường A/D.</p>
  const latest = [...points].reverse().find((point) => point.value !== null)
  return <div><svg viewBox="0 0 600 180" preserveAspectRatio="none" aria-hidden="true" className="h-44 w-full"><line x1="0" x2="600" y1="170" y2="170" stroke="hsl(var(--foreground) / .12)" />{paths.map((path, index) => <path key={index} d={path} fill="none" stroke="hsl(var(--widget))" strokeWidth="2" vectorEffect="non-scaling-stroke" />)}</svg><p className="mt-2 text-meta text-ink-5">Điểm gần nhất: <span className="font-mono text-ink-2">{latest?.value?.toLocaleString("vi-VN") ?? "—"}</span>{latest ? ` · ${latest.session_date}` : ""}. Khoảng trống là phiên thiếu dữ liệu, không nội suy.</p></div>
}
