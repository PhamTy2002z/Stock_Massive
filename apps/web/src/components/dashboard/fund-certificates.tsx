"use client"

import { cn } from "@/lib/utils"
import { useFundCertificates } from "@/hooks/use-fund-certificates"
import { SurfaceCard } from "./ui-kit"

const dash = "—"

const formatNav = (value: number | null) =>
  value === null
    ? dash
    : value.toLocaleString("vi-VN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const formatChange = (value: number | null) =>
  value === null
    ? dash
    : `${value >= 0 ? "+" : "−"}${Math.abs(value).toLocaleString("vi-VN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}%`

/**
 * NAV per certificate for the listed funds — the passive counterpart to the
 * VN30 board above it, for readers comparing "buy the index" against picking.
 */
export function FundCertificates({ className }: { className?: string }) {
  const { data, isLoading } = useFundCertificates()

  if (isLoading) {
    return <FundCertificatesSkeleton className={className} />
  }

  const funds = data?.funds ?? []

  return (
    <SurfaceCard className={className}>
      <div className="flex flex-wrap items-baseline justify-between gap-4 pb-2">
        <span className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px]">
          Chứng chỉ quỹ
        </span>
        <span className="text-[13px] leading-[1.43] tracking-[-0.224px] text-muted-foreground">
          NAV/CCQ
        </span>
      </div>

      {funds.length === 0 ? (
        <p className="border-t border-[hsl(var(--hairline))] py-4 text-[13px] leading-[1.43] tracking-[-0.224px] text-muted-foreground">
          Chưa có dữ liệu chứng chỉ quỹ.
        </p>
      ) : (
        funds.map((fund) => {
          const change = fund.change_pct

          return (
            <div
              key={fund.symbol}
              className="grid grid-cols-[1fr_auto_auto] items-center gap-4 border-t border-[hsl(var(--hairline))] py-2.5"
            >
              <span className="truncate text-[15px] font-semibold leading-[1.24] tracking-[-0.374px]">
                {fund.symbol}
              </span>
              <span className="text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums">
                {formatNav(fund.nav)}
              </span>
              <span
                className={cn(
                  "min-w-[72px] text-right text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums",
                  change === null
                    ? "text-muted-foreground"
                    : change >= 0
                      ? "text-positive"
                      : "text-negative"
                )}
              >
                {formatChange(change)}
              </span>
            </div>
          )
        })
      )}
    </SurfaceCard>
  )
}

export function FundCertificatesSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-[340px] animate-pulse rounded-card border border-border bg-card",
        className
      )}
    />
  )
}
