"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { ChevronLeft, ChevronRight, TrendingDown, TrendingUp } from "lucide-react"
import { cn } from "@/lib/utils"
import { useVN30Overview } from "@/hooks/use-vn30-overview"
import type { VN30OverviewItem } from "@/lib/api"
import { FilterChip, RefreshButton, SectionHeader, SurfaceCard } from "./ui-kit"

interface VN30OverviewTableProps {
  className?: string
}

/** How the board is ordered. Each answers a different question about the day. */
type SortKey = "market_cap" | "change_pct" | "volume"

const sorts: { key: SortKey; label: string }[] = [
  { key: "market_cap", label: "Vốn hoá" },
  { key: "change_pct", label: "Tăng mạnh" },
  { key: "volume", label: "Thanh khoản" },
]

const ROWS_PER_PAGE = 10
const COLUMNS = "64px minmax(190px,1fr) 96px 92px 106px 132px"

const dash = "—"

const formatPrice = (value: number | null) =>
  value === null ? dash : value.toLocaleString("vi-VN", { maximumFractionDigits: 0 })

const formatPercent = (value: number | null) =>
  value === null
    ? dash
    : `${value >= 0 ? "+" : "−"}${Math.abs(value).toLocaleString("vi-VN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}%`

const formatVolume = (value: number | null) =>
  value === null
    ? dash
    : `${(value / 1_000_000).toLocaleString("vi-VN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}M`

const formatMarketCap = (value: number | null) =>
  value === null ? dash : `${value.toLocaleString("vi-VN", { maximumFractionDigits: 0 })} tỷ`

function Row({ stock }: { stock: VN30OverviewItem }) {
  const change = stock.change_pct
  const isUp = (change ?? 0) >= 0
  const Trend = isUp ? TrendingUp : TrendingDown

  return (
    <Link
      href={`/analytics/deep-dive?symbol=${encodeURIComponent(stock.symbol)}`}
      style={{ gridTemplateColumns: COLUMNS }}
      className="-mx-2.5 grid min-w-[700px] items-center gap-3 rounded-lg border-t border-[hsl(var(--hairline))] px-2.5 py-2.5 transition-colors duration-150 hover:bg-muted"
    >
      <span className="text-[15px] font-semibold leading-[1.24] tracking-[-0.374px]">
        {stock.symbol}
      </span>
      <span className="truncate text-[15px] leading-[1.47] tracking-[-0.374px] text-foreground/80">
        {stock.company_name}
      </span>
      <span className="text-right text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums">
        {formatPrice(stock.price)}
      </span>
      <span
        className={cn(
          "flex items-center justify-end gap-1.5 text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums",
          change === null ? "text-muted-foreground" : isUp ? "text-positive" : "text-negative"
        )}
      >
        {change !== null && <Trend aria-hidden className="size-[13px]" />}
        {formatPercent(change)}
      </span>
      <span className="text-right text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums text-muted-foreground">
        {formatVolume(stock.volume)}
      </span>
      <span className="text-right text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums text-muted-foreground">
        {formatMarketCap(stock.market_cap)}
      </span>
    </Link>
  )
}

export function VN30OverviewTable({ className }: VN30OverviewTableProps) {
  const { data, isPending, isFetching, refetch } = useVN30Overview()
  const [sortKey, setSortKey] = useState<SortKey>("market_cap")
  const [page, setPage] = useState(1)

  const stocks = useMemo(() => {
    const items = [...(data?.stocks ?? [])]
    // Nulls sort last whichever column is active: a missing figure is not a
    // small figure, and letting it rank as zero would put it on top of "Tăng mạnh".
    return items.sort((a, b) => {
      const left = a[sortKey]
      const right = b[sortKey]
      if (left === null) return 1
      if (right === null) return -1
      return right - left
    })
  }, [data?.stocks, sortKey])

  const totalPages = Math.max(1, Math.ceil(stocks.length / ROWS_PER_PAGE))
  const currentPage = Math.min(page, totalPages)
  const start = (currentPage - 1) * ROWS_PER_PAGE
  const visible = stocks.slice(start, start + ROWS_PER_PAGE)

  const changeSort = (key: SortKey) => {
    setSortKey(key)
    setPage(1)
  }

  return (
    <section className={cn("min-w-0", className)}>
      <SectionHeader title="Tổng quan VN30">
        {sorts.map((sort) => (
          <FilterChip
            key={sort.key}
            label={sort.label}
            isActive={sortKey === sort.key}
            onClick={() => changeSort(sort.key)}
          />
        ))}
        <RefreshButton
          onClick={() => void refetch()}
          isRefreshing={isFetching}
          label="bảng VN30"
        />
      </SectionHeader>

      <SurfaceCard className="overflow-x-auto px-[18px] pb-[18px] pt-1">
        <div
          style={{ gridTemplateColumns: COLUMNS }}
          className="grid min-w-[700px] items-center gap-3 py-3 text-[13px] font-semibold leading-[1.29] tracking-[-0.224px] text-muted-foreground"
        >
          <span>Mã</span>
          <span>Tên công ty</span>
          <span className="text-right">Giá</span>
          <span className="text-right">%</span>
          <span className="text-right">Khối lượng</span>
          <span className="text-right">Vốn hoá</span>
        </div>

        {isPending ? (
          <div className="min-w-[700px] space-y-3 py-2">
            {[...Array(ROWS_PER_PAGE)].map((_, i) => (
              <div key={i} className="h-6 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <p className="py-8 text-center text-[15px] leading-[1.47] tracking-[-0.374px] text-muted-foreground">
            Chưa có dữ liệu rổ VN30 cho phiên này.
          </p>
        ) : (
          visible.map((stock) => <Row key={stock.symbol} stock={stock} />)
        )}

        <div className="mt-1.5 flex min-w-[700px] flex-wrap items-center justify-between gap-6 border-t border-[hsl(var(--hairline))] pt-4">
          <span className="text-[13px] leading-[1.43] tracking-[-0.224px] text-muted-foreground">
            {stocks.length === 0
              ? "0 cổ phiếu"
              : `${start + 1}–${Math.min(start + ROWS_PER_PAGE, stocks.length)} trên ${stocks.length} cổ phiếu`}
          </span>
          <div className="flex items-center gap-4">
            <span className="text-[13px] leading-[1.43] tracking-[-0.224px] text-muted-foreground">
              Trang {currentPage}/{totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage(currentPage - 1)}
              disabled={currentPage === 1}
              aria-label="Trang trước"
              className="flex size-9 items-center justify-center rounded-full border border-[hsl(var(--hairline))] bg-muted/40 text-muted-foreground transition-transform duration-150 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <ChevronLeft className="size-4" />
            </button>
            <button
              type="button"
              onClick={() => setPage(currentPage + 1)}
              disabled={currentPage === totalPages}
              aria-label="Trang sau"
              className="flex size-9 items-center justify-center rounded-full bg-interactive-strong text-white transition-transform duration-150 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>
      </SurfaceCard>
    </section>
  )
}

export function VN30OverviewTableSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="mb-3.5 h-8 w-48 animate-pulse rounded bg-muted" />
      <div className="h-[520px] animate-pulse rounded-[18px] border border-border bg-card" />
    </div>
  )
}
