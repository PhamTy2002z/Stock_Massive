"use client"

import Link from "next/link"
import { useSectorPeers } from "@/hooks/use-sector-peers"
import type { StockDetail } from "@/lib/api"
import { cn } from "@/lib/utils"

interface StockProfileSidebarProps {
  stock: StockDetail
  className?: string
}

const decimal = (value: number, digits = 2) =>
  value.toLocaleString("vi-VN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })

/** Market cap arrives in đồng; the board quotes it in tỷ. */
function formatMarketCap(value: number): string {
  const billions = value / 1_000_000_000
  if (billions >= 1_000_000) return `${decimal(billions / 1_000_000)} triệu tỷ`
  return `${Math.round(billions).toLocaleString("vi-VN")} tỷ`
}

function formatShares(value: number): string {
  const billions = value / 1_000_000_000
  if (billions >= 1) return `${decimal(billions)} tỷ`
  return `${decimal(value / 1_000_000, 1)} triệu`
}

function Panel({
  title,
  children,
  className,
}: {
  title: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("rounded-[18px] border border-border bg-card p-[18px]", className)}>
      <div className="pb-1 text-[13px] font-semibold leading-[1.29] tracking-[-0.208px] text-muted-foreground">
        {title}
      </div>
      {children}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-t border-[hsl(var(--hairline))] py-[9px]">
      <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
        {label}
      </span>
      <span className="text-right text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums">
        {value}
      </span>
    </div>
  )
}

/** Sector peers, priced. Each row navigates to that ticker's own deep dive. */
function PeerList({ symbol }: { symbol: string }) {
  const { data } = useSectorPeers(symbol, 5)

  // The target itself is in the peer list; the panel is about the others.
  const peers = data.peers.filter((p) => p.symbol !== data.symbol).slice(0, 4)

  if (peers.length === 0) {
    return (
      <div className="py-2 text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
        Chưa tìm được mã cùng ngành để so sánh.
      </div>
    )
  }

  return (
    <>
      {peers.map((peer) => {
        const premium = peer.premium_pe

        return (
          <Link
            key={peer.symbol}
            href={`/analytics/deep-dive?symbol=${encodeURIComponent(peer.symbol)}`}
            className="flex items-baseline justify-between gap-3 border-t border-[hsl(var(--hairline))] py-[9px] transition-colors hover:bg-muted/50"
          >
            <span className="text-[15px] font-semibold leading-[1.24] tracking-[-0.374px]">
              {peer.symbol}
            </span>
            <span className="text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums text-muted-foreground">
              {peer.pe === null ? "—" : `P/E ${decimal(peer.pe)}`}
            </span>
            <span
              className={cn(
                "min-w-16 text-right text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums",
                premium === null
                  ? "text-muted-foreground"
                  : premium >= 0
                    ? "text-positive"
                    : "text-negative"
              )}
            >
              {premium === null
                ? "—"
                : `${premium >= 0 ? "+" : "−"}${decimal(Math.abs(premium), 1)}%`}
            </span>
          </Link>
        )
      })}
    </>
  )
}

/**
 * The right column of the deep dive: what the company is, then who it trades
 * beside. Both are reference material — they sit still while the tabs on the
 * left change.
 */
export function StockProfileSidebar({ stock, className }: StockProfileSidebarProps) {
  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <Panel title="Hồ sơ">
        {stock.exchange && <Row label="Sàn" value={stock.exchange} />}
        {stock.industry && <Row label="Ngành" value={stock.industry} />}
        {stock.market_cap !== null && (
          <Row label="Vốn hoá" value={formatMarketCap(stock.market_cap)} />
        )}
        {stock.outstanding_shares !== null && (
          <Row label="CP lưu hành" value={formatShares(stock.outstanding_shares)} />
        )}
        {stock.vn30_rank !== null && stock.vn30_rank !== undefined && (
          <Row label="Xếp hạng VN30" value={`#${stock.vn30_rank}`} />
        )}
      </Panel>

      <Panel title="Cùng ngành">
        <PeerList symbol={stock.symbol} />
      </Panel>
    </div>
  )
}

export function StockProfileSidebarSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="h-[248px] animate-pulse rounded-[18px] border border-border bg-card" />
      <div className="h-[196px] animate-pulse rounded-[18px] border border-border bg-card" />
    </div>
  )
}
