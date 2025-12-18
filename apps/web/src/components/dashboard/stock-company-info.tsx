"use client"

import { cn } from "@/lib/utils"

interface StockCompanyInfoProps {
  symbol: string
  industry: string
  marketCap: number // billion VND
  outstandingShares: number // billion shares
  exchange: string | null
  vn30Rank: number | null
  description: string
  className?: string
}

// Format market cap
function formatMarketCap(value: number): string {
  if (value >= 1000) {
    return `${(value / 1000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} nghìn tỷ`
  }
  return `${value.toLocaleString("vi-VN", { maximumFractionDigits: 1 })} tỷ`
}

// Format shares
function formatShares(value: number): string {
  return `${value.toLocaleString("vi-VN", { maximumFractionDigits: 1 })} tỷ`
}

export function StockCompanyInfo({
  symbol,
  industry,
  marketCap,
  outstandingShares,
  exchange,
  vn30Rank,
  description,
  className,
}: StockCompanyInfoProps) {
  return (
    <div className={cn("rounded-lg border bg-card", className)}>
      {/* Info Table */}
      <div className="divide-y divide-border">
        <InfoRow label="Mã cổ phiếu" value={symbol} />
        <InfoRow label="Ngành" value={industry} />
        <InfoRow label="Vốn hóa" value={formatMarketCap(marketCap)} />
        <InfoRow label="CP lưu hành" value={formatShares(outstandingShares)} />
        <InfoRow label="Sàn giao dịch" value={exchange || "N/A"} />
        <InfoRow label="Top vốn hoá VN30" value={vn30Rank ? `#${vn30Rank}` : "-"} />
      </div>

      {/* Description */}
      <div className="p-4 border-t border-border">
        <p className="text-sm text-muted-foreground line-clamp-4">
          {description}
        </p>
        <button className="mt-2 text-sm text-primary hover:underline cursor-pointer">
          Xem chi tiết
        </button>
      </div>
    </div>
  )
}

// Info Row Component
function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground text-right">{value}</span>
    </div>
  )
}
