"use client"

import { useFundCertificates } from "@/hooks/use-fund-certificates"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertCircle, RefreshCw, TrendingUp, TrendingDown } from "lucide-react"
import { cn } from "@/lib/utils"

interface FundCertificatesProps {
  className?: string
}

export function FundCertificates({ className }: FundCertificatesProps) {
  const { data, isLoading, error, refetch } = useFundCertificates()

  // Get first 7 funds for display
  const funds = data?.funds?.slice(0, 7) ?? []

  if (isLoading && !data) {
    return <FundCertificatesSkeleton />
  }

  if (error) {
    return (
      <div className={cn("rounded-lg border bg-card p-6 text-center", className)}>
        <AlertCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
        <p className="text-sm text-muted-foreground mb-3">{error.message}</p>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
        >
          <RefreshCw className="h-4 w-4" />
          Thử lại
        </button>
      </div>
    )
  }

  if (!data || funds.length === 0) {
    return (
      <div className={cn("rounded-lg border bg-card p-6 text-center", className)}>
        <p className="text-sm text-muted-foreground">Không có dữ liệu chứng chỉ quỹ</p>
      </div>
    )
  }

  return (
    <div className={cn("rounded-lg border bg-card overflow-hidden", className)}>
      {/* Table Header */}
      <div className="grid grid-cols-[1fr_auto_auto] gap-4 px-4 py-3 bg-muted/50 border-b text-xs font-medium text-muted-foreground">
        <span>Mã quỹ</span>
        <span className="text-right w-20">NAV/CCQ</span>
        <span className="text-right w-16">%</span>
      </div>
      {/* Table Body */}
      <div className="divide-y divide-border">
        {funds.map((fund) => (
          <FundRow
            key={fund.symbol}
            symbol={fund.symbol}
            fundType={fund.fund_type}
            nav={fund.nav}
            changePct={fund.change_pct}
          />
        ))}
      </div>
    </div>
  )
}

interface FundRowProps {
  symbol: string
  fundType: string | null
  nav: number | null
  changePct: number | null
}

function FundRow({ symbol, fundType, nav, changePct }: FundRowProps) {
  const isPositive = changePct !== null && changePct > 0
  const isNegative = changePct !== null && changePct < 0
  const isNeutral = changePct === null || changePct === 0

  return (
    <div
      className={cn(
        "grid grid-cols-[1fr_auto_auto] gap-4 px-4 py-3 transition-colors border-l-2",
        isPositive && "border-l-emerald-500 dark:border-l-emerald-400 bg-emerald-500/5 dark:bg-emerald-400/5 hover:bg-emerald-500/10 dark:hover:bg-emerald-400/10",
        isNegative && "border-l-red-500 dark:border-l-red-400 bg-red-500/5 dark:bg-red-400/5 hover:bg-red-500/10 dark:hover:bg-red-400/10",
        isNeutral && "border-l-transparent hover:bg-muted/30"
      )}
    >
      <div className="min-w-0">
        <span className="text-sm font-medium text-foreground truncate block">{symbol}</span>
        <span className="text-xs text-muted-foreground truncate block">{formatFundType(fundType)}</span>
      </div>
      <span className="text-sm font-medium tabular-nums text-foreground text-right w-20">
        {nav ? formatNav(nav) : "N/A"}
      </span>
      <div className="flex items-center justify-end gap-1 w-16">
        {isPositive && <TrendingUp className="h-3 w-3 text-emerald-500 dark:text-emerald-400" />}
        {isNegative && <TrendingDown className="h-3 w-3 text-red-500 dark:text-red-400" />}
        <span
          className={cn(
            "text-sm font-medium tabular-nums",
            isPositive && "text-emerald-500 dark:text-emerald-400",
            isNegative && "text-red-500 dark:text-red-400",
            isNeutral && "text-muted-foreground"
          )}
        >
          {changePct !== null ? formatChangePct(changePct) : "N/A"}
        </span>
      </div>
    </div>
  )
}

function FundCertificatesSkeleton() {
  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      {/* Header skeleton */}
      <div className="grid grid-cols-[1fr_auto_auto] gap-4 px-4 py-3 bg-muted/50 border-b">
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-3 w-16" />
      </div>
      {/* Body skeleton */}
      <div className="divide-y divide-border">
        {[...Array(7)].map((_, i) => (
          <div key={i} className="grid grid-cols-[1fr_auto_auto] gap-4 px-4 py-3 border-l-2 border-l-transparent">
            <div>
              <Skeleton className="h-4 w-20 mb-1" />
              <Skeleton className="h-3 w-14" />
            </div>
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-16" />
          </div>
        ))}
      </div>
    </div>
  )
}

// Format fund type to Vietnamese
function formatFundType(type: string | null): string {
  if (!type) return "N/A"
  const typeMap: Record<string, string> = {
    STOCK: "Cổ phiếu",
    BOND: "Trái phiếu",
    BALANCED: "Cân bằng",
  }
  return typeMap[type.toUpperCase()] || type
}

// Format NAV with Vietnamese locale
function formatNav(value: number): string {
  return value.toLocaleString("vi-VN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })
}

// Format change percentage with sign
function formatChangePct(value: number): string {
  const sign = value > 0 ? "+" : ""
  return `${sign}${value.toFixed(2)}%`
}

export { FundCertificatesSkeleton }
