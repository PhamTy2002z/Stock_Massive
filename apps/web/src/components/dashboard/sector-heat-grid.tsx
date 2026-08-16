"use client"

import { useSectorPerformance } from "@/hooks/use-sector-performance"
import { cn } from "@/lib/utils"
import { RefreshButton, SectionHeader } from "./ui-kit"

/**
 * Every sector in one grid, ordered worst to best.
 *
 * The two Top-5 cards answer "what led and what dragged". This answers the
 * question they cannot: *how much of the market moved at all* — a wall that is
 * mostly red says something a five-row list never does, and it says it before
 * a single number has been read.
 *
 * Tint carries the magnitude and the sign; the printed percentage carries the
 * value. That pairing is deliberate — the tint alone would put meaning in
 * colour, which this system does not do anywhere else either.
 */

// The move, in percent, at which a tile reaches full strength. Past it the
// tint stops deepening: one runaway sector must not flatten every other tile
// into a shade nobody can tell from zero.
const FULL_TINT_AT = 3
const MAX_TINT = 0.28

const percent = (value: number) =>
  `${value >= 0 ? "+" : "−"}${Math.abs(value).toLocaleString("vi-VN", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`

function tint(changePct: number): string {
  const strength = Math.min(1, Math.abs(changePct) / FULL_TINT_AT) * MAX_TINT
  const token = changePct >= 0 ? "--positive" : "--negative"
  return `hsl(var(${token}) / ${strength.toFixed(3)})`
}

export function SectorHeatGrid({ className }: { className?: string }) {
  const { data, isPending, isFetching, refetch } = useSectorPerformance()

  const sectors = [...(data?.sectors ?? [])].sort((a, b) => a.change_pct - b.change_pct)

  if (isPending) {
    return <SectorHeatGridSkeleton className={className} />
  }

  return (
    <section className={cn("min-w-0", className)}>
      <SectionHeader title="Nhiệt độ ngành">
        <span className="text-meta text-muted-foreground">
          % thay đổi · {sectors.length} ngành
        </span>
        <RefreshButton
          onClick={() => void refetch()}
          isRefreshing={isFetching}
          label="nhiệt độ ngành"
        />
      </SectionHeader>

      {sectors.length === 0 ? (
        <div className="rounded-card border border-border bg-card p-[14px]">
          <p className="text-center text-control text-muted-foreground">
            Chưa có dữ liệu ngành cho phiên này.
          </p>
        </div>
      ) : (
        <div className="grid min-w-0 grid-cols-[repeat(auto-fit,minmax(112px,1fr))] gap-[7px]">
          {sectors.map((sector) => (
            <div
              key={sector.icb_code}
              style={{ background: tint(sector.change_pct) }}
              className="min-w-0 rounded-[10px] p-[10px] shadow-[inset_0_0_0_1px_hsl(var(--foreground)/0.05)]"
            >
              <div className="truncate text-micro text-ink-2" title={sector.icb_name}>
                {sector.icb_name}
              </div>
              <div
                className={cn(
                  "mt-1 font-mono text-row font-semibold tabular-nums",
                  sector.change_pct >= 0 ? "text-positive" : "text-negative"
                )}
              >
                {percent(sector.change_pct)}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export function SectorHeatGridSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="mb-3.5 h-6 w-40 animate-pulse rounded bg-foreground/[0.07]" />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(112px,1fr))] gap-[7px]">
        {Array.from({ length: 12 }).map((_, index) => (
          <div key={index} className="h-[62px] animate-pulse rounded-[10px] bg-foreground/[0.07]" />
        ))}
      </div>
    </div>
  )
}
