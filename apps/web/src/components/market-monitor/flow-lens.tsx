"use client"

import { useMarketFlows } from "@/hooks/use-market-monitor"
import type { FlowMonitorRow, MetricValue } from "@/lib/market-monitor/api"
import type { MarketMonitorUrlApi } from "@/lib/market-monitor/url-state"
import { cn } from "@/lib/utils"
import { useShell } from "@/components/shell/shell-state"

import { CoverageLine, directionClass, EvidencePanel, formatMetric, LensEmpty, LensError, LensLoading, MetricReading, MonitorStateNotice, SectionHeading, signedMetric } from "./monitor-primitives"
import { useReportMonitorStatus } from "./monitor-status"

export function FlowLens({ url }: { url: MarketMonitorUrlApi }) {
  const query = useMarketFlows({ exchange: url.state.exchange, asOf: url.state.asOf, horizon: url.state.horizon })
  useReportMonitorStatus(query.data?.meta, query.isFetching)
  if (query.isPending) return <FlowPanel><LensLoading /></FlowPanel>
  if (query.isError || !query.data) return <FlowPanel><LensError retry={() => void query.refetch()} message={query.error?.message} /></FlowPanel>
  const data = query.data
  return <div id="monitor-panel-flow" aria-labelledby="monitor-tab-flow" className="grid gap-[18px]" role="tabpanel" aria-label="Dòng tiền thị trường">
    <MonitorStateNotice meta={data.meta} />
    <EvidencePanel>
      <SectionHeading detail="EOD khối ngoại · DNSE realtime tách biệt">So sánh dòng tiền</SectionHeading>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricReading label="Khối ngoại 1P" metric={data.foreign_net_1d_vnd} signed />
        <MetricReading label="Khối ngoại 5P" metric={data.foreign_net_5d_vnd} signed />
        <MetricReading label="Khối ngoại 20P" metric={data.foreign_net_20d_vnd} signed />
        <MetricReading label="Chủ động mua" metric={data.active_buy_share} />
      </div>
    </EvidencePanel>
    <div className="grid gap-3 lg:grid-cols-2">
      <FlowList title="Tiền vào" rows={data.inflows} horizon={url.state.horizon} />
      <FlowList title="Tiền ra" rows={data.outflows} horizon={url.state.horizon} />
    </div>
    <section><SectionHeading>Đảo chiều</SectionHeading>{data.reversals.length ? <FlowRows rows={data.reversals} horizon={url.state.horizon} /> : <LensEmpty>Không phát hiện đảo chiều đủ bằng chứng trong phạm vi này.</LensEmpty>}</section>
    <CoverageLine meta={data.meta} updating={query.isFetching} />
  </div>
}

function FlowPanel({ children }: { children: React.ReactNode }) { return <div id="monitor-panel-flow" aria-labelledby="monitor-tab-flow" role="tabpanel">{children}</div> }

function FlowList({ title, rows, horizon }: { title: string; rows: FlowMonitorRow[]; horizon: 1 | 5 | 20 }) {
  return <EvidencePanel><SectionHeading detail={`${rows.length} mã`}>{title}</SectionHeading>{rows.length ? <FlowRows rows={rows} horizon={horizon} /> : <p className="py-5 text-center text-meta text-ink-6">Không có mã đủ bằng chứng.</p>}</EvidencePanel>
}

function FlowRows({ rows, horizon }: { rows: FlowMonitorRow[]; horizon: 1 | 5 | 20 }) {
  const { dispatch } = useShell()
  return <div className="divide-y divide-hairline">{rows.map((row) => {
    const foreign = row[`foreign_net_${horizon}d_vnd`] as MetricValue
    return <button key={row.symbol} type="button" onClick={() => dispatch({ type: "select-symbol", selected: { symbol: row.symbol, name: row.symbol, exchange: row.exchange }, open: true })} className="grid min-h-14 w-full grid-cols-[58px_minmax(0,1fr)_auto] items-center gap-3 py-2.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring md:grid-cols-[58px_minmax(0,1fr)_110px_110px]"><span className="font-mono text-control font-semibold">{row.symbol}</span><span className="min-w-0"><span className={cn("block font-mono text-meta", directionClass(foreign.value))}>{signedMetric(foreign)}</span><span className="mt-0.5 block text-micro text-ink-6">{row.quadrant ?? "Chưa có góc phần tư realtime"}</span></span><span className="hidden text-right md:block"><span className="block text-micro text-ink-6">Ngoại / ADTV</span><span className="font-mono text-meta text-ink-2">{formatMetric(row.foreign_flow_over_adtv)}</span></span><span className="text-right"><span className="block text-micro text-ink-6">Chủ động / ADTV</span><span className="font-mono text-meta text-ink-2">{formatMetric(row.active_flow_over_adtv)}</span></span></button>
  })}</div>
}
