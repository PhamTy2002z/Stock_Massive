"use client"

import { useMarketSectors } from "@/hooks/use-market-monitor"
import type { SectorMonitorRow } from "@/lib/market-monitor/api"
import type { MarketMonitorUrlApi } from "@/lib/market-monitor/url-state"
import { cn } from "@/lib/utils"

import { CoverageLine, directionClass, formatMetric, LensEmpty, LensError, LensLoading, MonitorStateNotice, RotationLabel, SectionHeading, signedMetric } from "./monitor-primitives"
import { useReportMonitorStatus } from "./monitor-status"

export function SectorLens({ url }: { url: MarketMonitorUrlApi }) {
  const query = useMarketSectors({ exchange: url.state.exchange, asOf: url.state.asOf })
  useReportMonitorStatus(query.data?.meta, query.isFetching)
  if (query.isPending) return <SectorPanel><LensLoading /></SectorPanel>
  if (query.isError || !query.data) return <SectorPanel><LensError retry={() => void query.refetch()} message={query.error?.message} /></SectorPanel>
  const data = query.data
  const metric = `return_${url.state.horizon}d_pct` as const
  const relativeMetric = `relative_strength_${url.state.horizon}d_pct` as const
  const sectors = [...data.sectors].sort((a, b) => (b[metric].value ?? -Infinity) - (a[metric].value ?? -Infinity))
  return <div id="monitor-panel-sectors" aria-labelledby="monitor-tab-sectors" className="grid gap-[18px]" role="tabpanel" aria-label="Theo dõi ngành">
    <MonitorStateNotice meta={data.meta} />
    <section>
      <SectionHeading detail={`${sectors.length} ngành · ${url.state.horizon} phiên`}>Từ dẫn dắt đến tụt hậu</SectionHeading>
      {sectors.length ? <LeaderStrip sectors={sectors} metric={metric} /> : <LensEmpty>Không có ngành đủ bằng chứng trong phạm vi đã chọn.</LensEmpty>}
    </section>
    {sectors.length > 0 && <div className="overflow-hidden rounded-card bg-surface-raised shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.07)]">
      <div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[820px] border-collapse text-control"><thead><tr><Th align="left">Ngành</Th><Th sorted>Hiệu suất {url.state.horizon}P</Th><Th>Sức mạnh tương đối</Th><Th>Tỷ lệ tăng</Th><Th>Thanh khoản</Th><Th align="left">Luân chuyển</Th><Th>Coverage</Th></tr></thead><tbody>{sectors.map((row) => <SectorRow key={`${row.exchange}-${row.code}`} row={row} metric={metric} relativeMetric={relativeMetric} open={() => url.push({ lens: "stocks", sector: row.code, sort: `return_${url.state.horizon}d_pct`, direction: "desc" })} />)}</tbody></table></div>
      <div className="divide-y divide-hairline md:hidden">{sectors.map((row) => <button key={`${row.exchange}-${row.code}`} type="button" onClick={() => url.push({ lens: "stocks", sector: row.code, sort: `return_${url.state.horizon}d_pct`, direction: "desc" })} className="grid min-h-16 w-full grid-cols-[minmax(0,1fr)_auto] gap-2 px-3.5 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"><span><span className="block truncate text-control font-medium text-ink-1">{row.name}</span><span className="mt-1 block text-micro text-ink-5"><RotationLabel value={row.rotation} /> · {row.coverage.evaluated}/{row.coverage.eligible} mã</span></span><span className="text-right"><span className={cn("block font-mono text-control font-semibold", directionClass(row[metric].value))}>{signedMetric(row[metric])}</span><span className="mt-1 block font-mono text-micro text-ink-5">RS {signedMetric(row[relativeMetric])}</span></span></button>)}</div>
    </div>}
    <CoverageLine meta={data.meta} updating={query.isFetching} />
  </div>
}

function SectorPanel({ children }: { children: React.ReactNode }) { return <div id="monitor-panel-sectors" aria-labelledby="monitor-tab-sectors" role="tabpanel">{children}</div> }

function LeaderStrip({ sectors, metric }: { sectors: SectorMonitorRow[]; metric: "return_1d_pct" | "return_5d_pct" | "return_20d_pct" }) {
  const available = sectors.filter((row) => row[metric].value !== null)
  if (available.length === 0) return <LensEmpty>Chưa có lợi suất ngành để dựng dải so sánh.</LensEmpty>
  const values = available.map((row) => row[metric].value as number); const low = Math.min(...values); const high = Math.max(...values); const span = high - low || 1
  return <div className="flex min-h-11 overflow-hidden rounded-control bg-surface-raised shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.07)]">{available.map((row) => { const value = row[metric].value as number; return <div key={`${row.exchange}-${row.code}`} title={`${row.name}: ${signedMetric(row[metric])}`} className={cn("min-w-[3px]", value >= 0 ? "bg-positive/70" : "bg-negative/70")} style={{ flexGrow: 1 + Math.abs((value - low) / span) }} /> })}<span className="sr-only">Xếp từ {available[0]?.name} {signedMetric(available[0]?.[metric])} đến {available.at(-1)?.name} {signedMetric(available.at(-1)?.[metric])}.</span></div>
}

function Th({ children, align = "right", sorted = false }: { children: React.ReactNode; align?: "left" | "right"; sorted?: boolean }) { return <th scope="col" aria-sort={sorted ? "descending" : undefined} className={cn("border-b border-hairline px-3 py-2.5 text-meta font-medium text-ink-5", align === "left" ? "text-left" : "text-right")}>{children}</th> }
function SectorRow({ row, metric, relativeMetric, open }: { row: SectorMonitorRow; metric: "return_1d_pct" | "return_5d_pct" | "return_20d_pct"; relativeMetric: "relative_strength_1d_pct" | "relative_strength_5d_pct" | "relative_strength_20d_pct"; open: () => void }) { return <tr className="hover:bg-foreground/[0.025]"><td className="border-b border-hairline px-3 py-2.5"><button type="button" onClick={open} className="text-left font-medium text-ink-1 underline decoration-transparent underline-offset-4 hover:decoration-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{row.name}</button><span className="mt-0.5 block font-mono text-micro text-ink-6">{row.exchange}</span></td><Td className={directionClass(row[metric].value)}>{signedMetric(row[metric])}</Td><Td className={directionClass(row[relativeMetric].value)}>{signedMetric(row[relativeMetric])}</Td><Td>{formatMetric(row.advancing_pct)}</Td><Td>{formatMetric(row.liquidity_ratio)}</Td><td className="border-b border-hairline px-3 py-2.5"><RotationLabel value={row.rotation} /></td><Td>{row.coverage.evaluated}/{row.coverage.eligible}</Td></tr> }
function Td({ children, className }: { children: React.ReactNode; className?: string }) { return <td className={cn("border-b border-hairline px-3 py-2.5 text-right font-mono text-meta tabular-nums text-ink-2", className)}>{children}</td> }
