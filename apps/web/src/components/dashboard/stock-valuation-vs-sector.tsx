"use client"

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
      className={cn("min-w-0 rounded-[18px] border border-border bg-card p-[18px]", className)}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-4 pb-1.5">
        <span className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px]">
          Định giá so với ngành{sectorName ? ` ${sectorName}` : ""}
        </span>
        {peerCount !== null && (
          <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
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
        value: format(value, isPercent),
        peer: format(peer, isPercent),
        width: `${Math.min(100, (value / scale) * 100)}%`,
        medianAt: `${Math.min(100, (peer / scale) * 100)}%`,
      }
    })
    .filter((row): row is NonNullable<typeof row> => row !== null)

  if (rows.length === 0) {
    return (
      <Shell peerCount={null} sectorName={data.icb_name} className={className}>
        <div className="py-2 text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
          Chưa có chỉ số định giá nào công bố đủ để so với trung vị ngành.
        </div>
      </Shell>
    )
  }

  return (
    <Shell peerCount={data.peers.length} sectorName={data.icb_name} className={className}>
      {rows.map((row) => (
        <div
          key={row.label}
          className="grid grid-cols-[110px_minmax(120px,1fr)_88px_96px] items-center gap-3.5 border-t border-[hsl(var(--hairline))] py-[11px]"
        >
          <span className="text-[15px] leading-[1.47] tracking-[-0.374px]">{row.label}</span>
          <div className="relative h-1.5 rounded-full bg-[hsl(var(--hairline))]">
            <span
              style={{ width: row.width }}
              className="absolute inset-y-0 left-0 rounded-full bg-foreground"
            />
            <span
              style={{ left: row.medianAt }}
              title="Trung vị ngành"
              className="absolute -top-1 h-3.5 w-0.5 bg-muted-foreground"
            />
          </div>
          <span className="text-right text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums">
            {row.value}
          </span>
          <span className="text-right text-[13px] leading-[1.43] tracking-[-0.208px] tabular-nums text-muted-foreground">
            TV {row.peer}
          </span>
        </div>
      ))}
    </Shell>
  )
}

export function StockValuationVsSectorSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-[264px] min-w-0 animate-pulse rounded-[18px] border border-border bg-card",
        className
      )}
    />
  )
}
