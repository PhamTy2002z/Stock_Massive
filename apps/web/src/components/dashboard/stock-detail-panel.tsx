"use client"

import { cn } from "@/lib/utils"

interface StockDetailPanelProps {
  volume: number // Khối lượng (shares)
  exchange: string // Sàn giao dịch (HOSE, HNX, UPCOM)
  marketCap: number // Vốn hóa (billion VND)
  industry: string // Ngành
  className?: string
}

// Format number with Vietnamese locale
function formatNumber(value: number, decimals = 2): string {
  return value.toLocaleString("vi-VN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

// Format large numbers (billions)
function formatBillion(value: number): string {
  if (value >= 1000) {
    return `${formatNumber(value / 1000, 2)} nghìn tỷ`
  }
  return `${formatNumber(value, 2)} tỷ`
}

// Format volume (millions of shares)
function formatVolume(value: number): string {
  if (value >= 1000000) {
    return `${formatNumber(value / 1000000, 2)} triệu`
  }
  if (value >= 1000) {
    return `${formatNumber(value / 1000, 2)} nghìn`
  }
  return formatNumber(value, 0)
}

export function StockDetailPanel({
  volume,
  exchange,
  marketCap,
  industry,
  className,
}: StockDetailPanelProps) {
  return (
    <div className={cn("grid grid-cols-2 gap-3 sm:grid-cols-4", className)}>
      <StatCard label="Khối lượng" value={formatVolume(volume)} />
      <StatCard label="Sàn giao dịch" value={exchange || "N/A"} />
      <StatCard label="Vốn hóa" value={formatBillion(marketCap)} />
      <StatCard label="Ngành" value={industry} />
    </div>
  )
}

// Stat Card Component
function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-card px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1.5 text-sm font-semibold tabular-nums text-foreground">
        {value}
      </p>
    </div>
  )
}
