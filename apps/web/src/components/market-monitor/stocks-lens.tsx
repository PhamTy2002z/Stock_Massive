"use client"

import { useEffect, useMemo, useState } from "react"
import { ArrowDown, ArrowUp, X } from "lucide-react"

import { useMarketStocks } from "@/hooks/use-market-monitor"
import type { MetricValue, StockMonitorRow } from "@/lib/market-monitor/api"
import {
  STOCK_PRESETS,
  type MarketMonitorUrlApi,
  type StockPreset,
  type StockSort,
} from "@/lib/market-monitor/url-state"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useShell } from "@/components/shell/shell-state"

import {
  CoverageLine,
  directionClass,
  formatMetric,
  LensEmpty,
  LensError,
  LensLoading,
  MonitorStateNotice,
  SectionHeading,
  signedMetric,
} from "./monitor-primitives"
import { useReportMonitorStatus } from "./monitor-status"

const PRESET_LABELS: Record<StockPreset, string> = {
  overview: "Tổng hợp",
  trend: "Xu hướng",
  flow: "Dòng tiền",
  valuation: "Định giá",
}

const DEFAULT_SORT: Record<StockPreset, { sort: StockSort; direction: "asc" | "desc" }> = {
  overview: { sort: "return_20d_pct", direction: "desc" },
  trend: { sort: "return_20d_pct", direction: "desc" },
  flow: { sort: "foreign_net_20d_vnd", direction: "desc" },
  valuation: { sort: "symbol", direction: "asc" },
}

const SORT_LABELS: Record<StockSort, string> = {
  symbol: "Mã",
  return_1d_pct: "Hiệu suất 1P",
  return_5d_pct: "Hiệu suất 5P",
  return_20d_pct: "Hiệu suất 20P",
  liquidity_ratio: "Thanh khoản / BQ20",
  foreign_net_20d_vnd: "Khối ngoại 20P",
  foreign_flow_over_adtv: "Khối ngoại / ADTV",
}

const SORTS_BY_PRESET: Record<StockPreset, StockSort[]> = {
  overview: ["symbol", "return_1d_pct", "return_5d_pct", "return_20d_pct", "liquidity_ratio"],
  trend: ["symbol", "return_1d_pct", "return_5d_pct", "return_20d_pct"],
  flow: ["symbol", "foreign_net_20d_vnd", "foreign_flow_over_adtv", "return_20d_pct"],
  valuation: ["symbol"],
}

export function StocksLens({ url }: { url: MarketMonitorUrlApi }) {
  const input = {
    exchange: url.state.exchange,
    asOf: url.state.asOf,
    preset: url.state.preset,
    sector: url.state.sector,
    sort: url.state.sort,
    direction: url.state.direction,
  }
  const query = useMarketStocks(input)
  const rows = useMemo(() => query.data?.pages.flatMap((page) => page.items) ?? [], [query.data])
  const meta = query.data?.pages[0]?.meta
  const [sectorDraft, setSectorDraft] = useState(url.state.sector ?? "")
  useReportMonitorStatus(meta, query.isFetching)
  useEffect(() => setSectorDraft(url.state.sector ?? ""), [url.state.sector])

  if (query.isPending) return <StocksPanel><LensLoading /></StocksPanel>
  if (query.isError || !meta) return <StocksPanel><LensError retry={() => void query.refetch()} message={query.error?.message} /></StocksPanel>

  function selectPreset(preset: StockPreset) {
    url.replace({ preset, ...DEFAULT_SORT[preset] })
  }

  return <div id="monitor-panel-stocks" aria-labelledby="monitor-tab-stocks" className="grid gap-[18px]" role="tabpanel" aria-label="Theo dõi cổ phiếu">
    <MonitorStateNotice meta={meta} />
    <div className="flex flex-col gap-3 rounded-card bg-surface-raised p-3.5 shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.07)]">
      <div className="flex gap-1 overflow-x-auto" role="tablist" aria-label="Bộ chỉ tiêu cổ phiếu">
        {STOCK_PRESETS.map((preset) => <button key={preset} type="button" role="tab" aria-selected={url.state.preset === preset} onClick={() => selectPreset(preset)} className={cn("min-h-10 shrink-0 rounded-control px-3 text-control text-ink-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", url.state.preset === preset && "bg-foreground/[0.08] text-ink-1")}>{PRESET_LABELS[preset]}</button>)}
      </div>
      <div className="flex flex-wrap items-end gap-2.5 border-t border-hairline pt-3">
        <label className="grid gap-1 text-micro text-ink-5"><span>Ngành</span><input value={sectorDraft} maxLength={8} placeholder="Tất cả" onChange={(event) => setSectorDraft(event.target.value.toUpperCase())} onBlur={() => url.replace({ sector: sectorDraft.trim() || null })} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); url.replace({ sector: sectorDraft.trim() || null }) } }} className="h-9 w-32 rounded-control border border-border bg-surface-sunken px-2.5 font-mono text-control text-ink-1 outline-none placeholder:text-ink-6 focus-visible:ring-2 focus-visible:ring-ring" /></label>
        <label className="grid gap-1 text-micro text-ink-5"><span>Sắp xếp</span><select value={SORTS_BY_PRESET[url.state.preset].includes(url.state.sort) ? url.state.sort : DEFAULT_SORT[url.state.preset].sort} onChange={(event) => url.replace({ sort: event.target.value as StockSort })} className="h-9 rounded-control border border-border bg-surface-sunken px-2.5 text-control text-ink-1 outline-none focus-visible:ring-2 focus-visible:ring-ring">{SORTS_BY_PRESET[url.state.preset].map((sort) => <option key={sort} value={sort}>{SORT_LABELS[sort]}</option>)}</select></label>
        <button type="button" aria-label={url.state.direction === "desc" ? "Đổi sang tăng dần" : "Đổi sang giảm dần"} onClick={() => url.replace({ direction: url.state.direction === "desc" ? "asc" : "desc" })} className="flex h-9 items-center gap-1.5 rounded-control border border-border bg-surface-sunken px-2.5 text-control text-ink-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{url.state.direction === "desc" ? <ArrowDown className="size-3.5" /> : <ArrowUp className="size-3.5" />}{url.state.direction === "desc" ? "Giảm dần" : "Tăng dần"}</button>
        {url.state.sector && <button type="button" onClick={() => url.replace({ sector: null })} className="flex h-9 items-center gap-1.5 rounded-control bg-foreground/[0.07] px-2.5 text-meta text-ink-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Ngành {url.state.sector}<X className="size-3.5" aria-hidden="true" /></button>}
      </div>
    </div>

    <section>
      <SectionHeading detail={`${rows.length}/${meta.coverage.evaluated} mã đã tải`}>{PRESET_LABELS[url.state.preset]}</SectionHeading>
      {rows.length ? <StockResults rows={rows} preset={url.state.preset} /> : <LensEmpty>Không có cổ phiếu phù hợp với {url.state.exchange}{url.state.sector ? ` và ngành ${url.state.sector}` : ""}. Hãy xóa bộ lọc ngành hoặc đổi phạm vi.</LensEmpty>}
      {query.hasNextPage && <div className="mt-3 flex justify-center"><Button type="button" variant="outline" size="sm" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? "Đang tải thêm…" : "Xem thêm"}</Button></div>}
    </section>
    <CoverageLine meta={meta} updating={query.isFetching && !query.isFetchingNextPage} />
  </div>
}

function StocksPanel({ children }: { children: React.ReactNode }) { return <div id="monitor-panel-stocks" aria-labelledby="monitor-tab-stocks" role="tabpanel">{children}</div> }

function StockResults({ rows, preset }: { rows: StockMonitorRow[]; preset: StockPreset }) {
  return <div className="overflow-hidden rounded-card bg-surface-raised shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.07)]"><div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[760px] border-collapse text-control"><thead><tr><Th align="left">Mã / doanh nghiệp</Th><Th align="left">Ngành</Th>{columns(preset).map((column) => <Th key={column.key}>{column.label}</Th>)}</tr></thead><tbody>{rows.map((row) => <StockTableRow key={row.symbol} row={row} preset={preset} />)}</tbody></table></div><div className="divide-y divide-hairline md:hidden">{rows.map((row) => <StockMobileRow key={row.symbol} row={row} preset={preset} />)}</div></div>
}

const COLUMN_SETS: Record<StockPreset, Array<{ key: string; label: string; signed?: boolean }>> = {
  overview: [{ key: "return_1d_pct", label: "1P", signed: true }, { key: "return_5d_pct", label: "5P", signed: true }, { key: "return_20d_pct", label: "20P", signed: true }, { key: "liquidity_ratio", label: "TK / BQ20" }],
  trend: [{ key: "return_1d_pct", label: "1P", signed: true }, { key: "return_5d_pct", label: "5P", signed: true }, { key: "return_20d_pct", label: "20P", signed: true }, { key: "trend", label: "MA20 / 50 / 200" }],
  flow: [{ key: "foreign_net_20d_vnd", label: "Ngoại 20P", signed: true }, { key: "foreign_flow_over_adtv", label: "Ngoại / ADTV", signed: true }, { key: "return_20d_pct", label: "Giá 20P", signed: true }],
  valuation: [{ key: "pe", label: "P/E" }, { key: "pb", label: "P/B" }],
}
function columns(preset: StockPreset) { return COLUMN_SETS[preset] }

function StockTableRow({ row, preset }: { row: StockMonitorRow; preset: StockPreset }) {
  const { dispatch } = useShell(); const open = () => dispatch({ type: "select-symbol", selected: { symbol: row.symbol, name: row.name, exchange: row.exchange }, open: true })
  return <tr className="hover:bg-foreground/[0.025]"><td className="sticky left-0 border-b border-hairline bg-surface-raised px-3 py-2.5"><button type="button" onClick={open} className="text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><span className="block font-mono font-semibold text-ink-1">{row.symbol}</span><span className="mt-0.5 block max-w-[220px] truncate text-micro text-ink-5">{row.name}</span></button></td><td className="border-b border-hairline px-3 py-2.5 text-meta text-ink-4">{row.sector_name ?? "—"}</td>{columns(preset).map((column) => <Td key={column.key} metric={column.key === "trend" ? undefined : row.metrics[column.key]} signed={column.signed}>{column.key === "trend" ? trendSummary(row) : undefined}</Td>)}</tr>
}

function StockMobileRow({ row, preset }: { row: StockMonitorRow; preset: StockPreset }) { const { dispatch } = useShell(); const primary = columns(preset)[0]; const secondary = columns(preset)[1]; return <button type="button" onClick={() => dispatch({ type: "select-symbol", selected: { symbol: row.symbol, name: row.name, exchange: row.exchange }, open: true })} className="grid min-h-16 w-full grid-cols-[minmax(0,1fr)_auto] gap-3 px-3.5 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"><span className="min-w-0"><span className="block font-mono text-control font-semibold text-ink-1">{row.symbol}</span><span className="mt-1 block truncate text-micro text-ink-5">{row.sector_name ?? row.name}</span></span><span className="text-right"><span className={cn("block font-mono text-control font-semibold", primary?.signed && directionClass(row.metrics[primary.key]?.value))}>{primary?.key === "trend" ? trendSummary(row) : primary?.signed ? signedMetric(row.metrics[primary.key]) : formatMetric(row.metrics[primary?.key])}</span><span className="mt-1 block font-mono text-micro text-ink-5">{secondary?.label} {secondary?.key === "trend" ? trendSummary(row) : secondary?.signed ? signedMetric(row.metrics[secondary?.key]) : formatMetric(row.metrics[secondary?.key])}</span></span></button> }

function trendSummary(row: StockMonitorRow) { return [20, 50, 200].map((window) => { const value = row.trend[`above_ma${window}`]?.value; return value === null || value === undefined ? `MA${window} —` : `${value ? ">" : "<"}MA${window}` }).join(" · ") }
function Th({ children, align = "right" }: { children: React.ReactNode; align?: "left" | "right" }) { return <th scope="col" className={cn("border-b border-hairline px-3 py-2.5 text-meta font-medium text-ink-5", align === "left" ? "text-left" : "text-right")}>{children}</th> }
function Td({ metric, signed, children }: { metric?: MetricValue; signed?: boolean; children?: React.ReactNode }) { return <td className={cn("border-b border-hairline px-3 py-2.5 text-right font-mono text-meta tabular-nums text-ink-2", signed && directionClass(metric?.value))}>{children ?? (signed ? signedMetric(metric) : formatMetric(metric))}</td> }
