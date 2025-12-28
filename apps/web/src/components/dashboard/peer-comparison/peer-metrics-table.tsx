"use client"

import { cn } from "@/lib/utils"
import type { PeerMetrics } from "@/lib/api"

interface PeerMetricsTableProps {
  peers: PeerMetrics[]
  targetSymbol: string
}

function formatPercent(value: number | null): string {
  if (value === null) return "-"
  return `${(value * 100).toFixed(1)}%`
}

function formatRatio(value: number | null): string {
  if (value === null) return "-"
  return value.toFixed(1)
}

function formatMarketCap(value: number | null): string {
  if (value === null) return "-"
  if (value >= 1e12) return `${(value / 1e12).toFixed(0)}T`
  if (value >= 1e9) return `${(value / 1e9).toFixed(0)}B`
  return `${(value / 1e6).toFixed(0)}M`
}

function getHeatmapColor(value: number | null, avg: number, inverse: boolean = false): string {
  if (value === null) return ""
  const isAbove = inverse ? value < avg : value > avg
  return isAbove
    ? "bg-green-500/20 text-green-600 dark:text-green-400"
    : "bg-red-500/20 text-red-600 dark:text-red-400"
}

export function PeerMetricsTable({ peers, targetSymbol }: PeerMetricsTableProps) {
  // Calculate averages for heatmap
  const validRoe = peers.filter(p => p.roe !== null)
  const validRoa = peers.filter(p => p.roa !== null)
  const validPe = peers.filter(p => p.pe !== null)
  const validPb = peers.filter(p => p.pb !== null)

  const avgRoe = validRoe.length > 0 ? validRoe.reduce((s, p) => s + (p.roe || 0), 0) / validRoe.length : 0
  const avgRoa = validRoa.length > 0 ? validRoa.reduce((s, p) => s + (p.roa || 0), 0) / validRoa.length : 0
  const avgPe = validPe.length > 0 ? validPe.reduce((s, p) => s + (p.pe || 0), 0) / validPe.length : 0
  const avgPb = validPb.length > 0 ? validPb.reduce((s, p) => s + (p.pb || 0), 0) / validPb.length : 0

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border/50">
            <th className="py-2 px-3 text-left font-medium text-muted-foreground">Symbol</th>
            <th className="py-2 px-3 text-left font-medium text-muted-foreground">Company</th>
            <th className="py-2 px-3 text-right font-medium text-muted-foreground">ROE</th>
            <th className="py-2 px-3 text-right font-medium text-muted-foreground">ROA</th>
            <th className="py-2 px-3 text-right font-medium text-muted-foreground">P/E</th>
            <th className="py-2 px-3 text-right font-medium text-muted-foreground">P/B</th>
            <th className="py-2 px-3 text-right font-medium text-muted-foreground">MCap</th>
          </tr>
        </thead>
        <tbody>
          {peers.map((peer) => (
            <tr
              key={peer.symbol}
              className={cn(
                "border-b border-border/30 hover:bg-muted/20",
                peer.symbol === targetSymbol && "bg-white/10 border-white/30"
              )}
            >
              <td className="py-2 px-3">
                <span className={cn(
                  "font-semibold",
                  peer.symbol === targetSymbol && "text-white"
                )}>
                  {peer.symbol}
                </span>
              </td>
              <td className="py-2 px-3 text-muted-foreground max-w-[150px] truncate">
                {peer.company_name || "-"}
              </td>
              <td className={cn("py-2 px-3 text-right tabular-nums rounded", getHeatmapColor(peer.roe, avgRoe))}>
                {formatPercent(peer.roe)}
              </td>
              <td className={cn("py-2 px-3 text-right tabular-nums rounded", getHeatmapColor(peer.roa, avgRoa))}>
                {formatPercent(peer.roa)}
              </td>
              <td className={cn("py-2 px-3 text-right tabular-nums rounded", getHeatmapColor(peer.pe, avgPe, true))}>
                {formatRatio(peer.pe)}
              </td>
              <td className={cn("py-2 px-3 text-right tabular-nums rounded", getHeatmapColor(peer.pb, avgPb, true))}>
                {formatRatio(peer.pb)}
              </td>
              <td className="py-2 px-3 text-right tabular-nums">
                {formatMarketCap(peer.market_cap)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 text-xs text-muted-foreground">
        Legend: <span className="text-green-500">Green</span> = Above avg, <span className="text-red-500">Red</span> = Below avg (P/E, P/B: lower is better)
      </div>
    </div>
  )
}
