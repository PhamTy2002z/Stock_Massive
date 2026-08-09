"use client"

import { useMemo, useState } from "react"
import { cn } from "@/lib/utils"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { useShareholders } from "@/hooks/use-shareholders"
import type { ShareholderItem } from "@/lib/api"

interface ShareholdersTabContentProps {
  symbol?: string
  className?: string
}

const ROWS_PER_PAGE = 10

/** A disclosure older than this reads as history, not as current ownership. */
const STALE_AFTER_DAYS = 365

const shareFormat = (value: number) => {
  const millions = value / 1_000_000
  if (millions >= 1_000) {
    return `${(millions / 1_000).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} tỷ CP`
  }
  return `${millions.toLocaleString("vi-VN", { maximumFractionDigits: 2 })} triệu CP`
}

const percentFormat = (value: number) =>
  value < 0.01
    ? "<0,01%"
    : `${value.toLocaleString("vi-VN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`

function isStale(date: string | null): boolean {
  if (!date) return false
  const parsed = new Date(date)
  if (Number.isNaN(parsed.getTime())) return false
  return Date.now() - parsed.getTime() > STALE_AFTER_DAYS * 24 * 60 * 60 * 1000
}

function Card({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("min-w-0 rounded-[18px] border border-border bg-card p-[18px]", className)}>
      {children}
    </div>
  )
}

/**
 * Ownership as one bar: the named holders that clear 1%, then everything else.
 *
 * The design splits this by holder category (state / foreign / other), but the
 * shareholders endpoint returns no category field. Grouping by disclosed size is
 * the same question answered with data that actually exists, rather than a
 * classification guessed from names.
 */
function OwnershipBreakdown({ shareholders }: { shareholders: ShareholderItem[] }) {
  const named = shareholders.filter((s) => s.ownership_pct >= 1).slice(0, 5)
  const namedTotal = named.reduce((sum, s) => sum + s.ownership_pct, 0)
  const others = Math.max(0, 100 - namedTotal)

  const tones = [
    "bg-foreground",
    "bg-interactive",
    "bg-[hsl(var(--positive))]",
    "bg-[#7c3fae]",
    "bg-[#cf7a1a]",
  ]

  return (
    <Card>
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <span className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px]">
          Cơ cấu sở hữu
        </span>
        <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
          {named.length} cổ đông công bố trên 1%
        </span>
      </div>

      <div className="mt-3.5 flex h-2.5 gap-[3px]">
        {named.map((holder, i) => (
          <span
            key={holder.id || holder.name}
            style={{ flex: holder.ownership_pct }}
            className={cn("rounded-full", tones[i % tones.length])}
          />
        ))}
        <span style={{ flex: others }} className="rounded-full bg-border" />
      </div>

      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-[13px] leading-[1.43] tracking-[-0.208px] tabular-nums">
        {named.map((holder, i) => (
          <span key={holder.id || holder.name} className="flex items-center gap-[7px]">
            <span className={cn("size-2 rounded-full", tones[i % tones.length])} />
            {holder.name} {percentFormat(holder.ownership_pct)}
          </span>
        ))}
        <span className="flex items-center gap-[7px] text-muted-foreground">
          <span className="size-2 rounded-full bg-border" />
          Khác {percentFormat(others)}
        </span>
      </div>
    </Card>
  )
}

export function ShareholdersTabContent({
  symbol = "HAG",
  className,
}: ShareholdersTabContentProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const { data } = useShareholders(symbol)

  const shareholders = useMemo(() => data.shareholders ?? [], [data.shareholders])
  const totalItems = shareholders.length
  const totalPages = Math.max(1, Math.ceil(totalItems / ROWS_PER_PAGE))
  const startIndex = (currentPage - 1) * ROWS_PER_PAGE
  const endIndex = Math.min(startIndex + ROWS_PER_PAGE, totalItems)
  const currentData = shareholders.slice(startIndex, endIndex)

  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) setCurrentPage(page)
  }

  if (totalItems === 0) {
    return (
      <Card className={className}>
        <p className="py-6 text-center text-[15px] leading-[1.47] tracking-[-0.374px] text-muted-foreground">
          Không có dữ liệu cổ đông cho mã {symbol}
        </p>
      </Card>
    )
  }

  const columns = "minmax(200px,1.6fr) 132px 92px 132px"

  return (
    <div className={cn("flex min-w-0 flex-col gap-4", className)}>
      <OwnershipBreakdown shareholders={shareholders} />

      <Card className="overflow-x-auto py-2">
        <div
          style={{ gridTemplateColumns: columns }}
          className="grid min-w-[620px] items-center gap-3.5 py-3.5 text-[13px] font-semibold leading-[1.29] tracking-[-0.208px] text-muted-foreground"
        >
          <span>Cổ đông</span>
          <span className="text-right">Số lượng</span>
          <span className="text-right">Tỷ lệ</span>
          <span className="text-right">Cập nhật</span>
        </div>

        {currentData.map((shareholder, index) => {
          const stale = isStale(shareholder.update_date)

          return (
            <div
              key={shareholder.id || `${shareholder.name}-${startIndex + index}`}
              style={{ gridTemplateColumns: columns }}
              className="grid min-w-[620px] items-center gap-3.5 border-t border-[hsl(var(--hairline))] py-[11px]"
            >
              <span className="truncate text-[15px] leading-[1.47] tracking-[-0.374px]">
                {shareholder.name}
              </span>
              <span className="text-right text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums">
                {shareFormat(shareholder.shares)}
              </span>
              <span
                className={cn(
                  "text-right text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums",
                  shareholder.ownership_pct < 0.01 && "text-muted-foreground"
                )}
              >
                {percentFormat(shareholder.ownership_pct)}
              </span>
              {/* A stale disclosure is flagged in amber rather than hidden: the
                  number is still the latest one filed, just not recent. */}
              <span
                className={cn(
                  "text-right text-[13px] leading-[1.43] tracking-[-0.208px] tabular-nums",
                  stale ? "text-[#cf7a1a]" : "text-muted-foreground"
                )}
              >
                {shareholder.update_date ?? "—"}
                {stale ? " · cũ" : ""}
              </span>
            </div>
          )
        })}

        <div className="mt-1.5 flex min-w-[620px] flex-wrap items-center justify-between gap-6 border-t border-[hsl(var(--hairline))] pt-4">
          <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
            {startIndex + 1}–{endIndex} trên {totalItems} cổ đông
          </span>
          <div className="flex items-center gap-3.5">
            <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
              Trang {currentPage}/{totalPages}
            </span>
            <button
              type="button"
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage === 1}
              aria-label="Trang trước"
              className="flex size-9 items-center justify-center rounded-full border border-[hsl(var(--hairline))] bg-muted/40 text-muted-foreground transition-transform duration-150 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <ChevronLeft className="size-4" />
            </button>
            <button
              type="button"
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage === totalPages}
              aria-label="Trang sau"
              className="flex size-9 items-center justify-center rounded-full bg-interactive text-white transition-transform duration-150 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>
      </Card>
    </div>
  )
}

// Skeleton for loading state
export function ShareholdersTabContentSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-4", className)}>
      <div className="h-[148px] animate-pulse rounded-[18px] border border-border bg-card" />
      <div
        className={cn(
          "h-[520px] animate-pulse rounded-[18px] border border-border bg-card",
          className
        )}
      />
    </div>
  )
}
