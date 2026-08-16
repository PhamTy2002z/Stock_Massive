"use client"

import { ComparisonBars } from "@/components/charts"
import { useSectorPeers } from "@/hooks/use-sector-peers"
import type { PeerMetrics, SectorMedian } from "@/lib/api"
import { cn } from "@/lib/utils"

interface StockValuationVsSectorProps {
  symbol: string
  className?: string
}

type MetricKey = "pe" | "pb" | "ps" | "roe" | "roa"

// P/S drops out on its own for banks: the provider does not publish a revenue
// multiple for them, so the median comes back null and the row never renders.
const metrics: { key: MetricKey; label: string; isPercent?: boolean }[] = [
  { key: "pe", label: "P/E" },
  { key: "pb", label: "P/B" },
  { key: "ps", label: "P/S" },
  { key: "roe", label: "ROE", isPercent: true },
  { key: "roa", label: "ROA", isPercent: true },
]

const format = (value: number, isPercent?: boolean) =>
  `${value.toLocaleString("vi-VN", {
    minimumFractionDigits: isPercent ? 1 : 2,
    maximumFractionDigits: isPercent ? 1 : 2,
  })}${isPercent ? "%" : ""}`

function Shell({
  peerCount,
  sectorName,
  children,
  className,
}: {
  peerCount: number | null
  sectorName: string | null
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn("min-w-0 rounded-card border border-border bg-card p-[14px]", className)}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-4 pb-1.5">
        <span className="text-[1.05rem] font-semibold leading-[1.24]">
          Định giá so với ngành{sectorName ? ` ${sectorName}` : ""}
        </span>
        {peerCount !== null && (
          <span className="text-meta text-muted-foreground">
            Trung vị {peerCount} mã cùng ngành
          </span>
        )}
      </div>
      {children}
    </div>
  )
}

/**
 * Each metric as a bar against its sector median, so "expensive" or "cheap" is a
 * glance rather than a subtraction. The bar is the stock, the tick is the median;
 * both are scaled to the same axis per row, which is what makes the gap readable.
 */
export function StockValuationVsSector({ symbol, className }: StockValuationVsSectorProps) {
  const { data } = useSectorPeers(symbol)

  const self: PeerMetrics | undefined = data.peers.find((p) => p.symbol === data.symbol)
  const median: SectorMedian = data.sector_median

  const rows = metrics
    .map(({ key, label, isPercent }) => {
      const value = self?.[key] ?? null
      const peer = median[key] ?? null
      if (value === null || peer === null) return null

      // Headroom above the larger of the two so the longer bar never fills the
      // track edge-to-edge and the median tick stays visible next to it.
      const scale = Math.max(value, peer) * 1.3
      if (scale <= 0) return null

      return {
        label,
        display: format(value, isPercent),
        trailing: `TV ${format(peer, isPercent)}`,
        percent: Math.min(100, (value / scale) * 100),
        markerPercent: Math.min(100, (peer / scale) * 100),
        markerLabel: "Trung vị ngành",
      }
    })
    .filter((row): row is NonNullable<typeof row> => row !== null)

  if (rows.length === 0) {
    return (
      <Shell peerCount={null} sectorName={data.icb_name} className={className}>
        <div className="py-2 text-meta text-muted-foreground">
          Chưa có chỉ số định giá nào công bố đủ để so với trung vị ngành.
        </div>
      </Shell>
    )
  }

  return (
    <Shell peerCount={data.peers.length} sectorName={data.icb_name} className={className}>
      {/* The flattening above is this card's; the drawing is the shared leaf,
          with the colours this card has always used passed into it. */}
      <ComparisonBars
        rows={rows}
        barColor="hsl(var(--foreground))"
        trackColor="hsl(var(--hairline))"
        markerColor="hsl(var(--muted-foreground))"
        rowClassName="grid grid-cols-[110px_minmax(120px,1fr)_88px_96px] items-center gap-3.5 border-t border-hairline py-[11px]"
        labelClassName="text-[0.95rem]"
        valueClassName="text-right text-[0.95rem]"
        trailingClassName="text-right text-meta text-muted-foreground"
      />
    </Shell>
  )
}

export function StockValuationVsSectorSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-[264px] min-w-0 animate-pulse rounded-card border border-border bg-card",
        className
      )}
    />
  )
}
