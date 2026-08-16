"use client"

import { cn } from "@/lib/utils"
import { useSectorPerformance } from "@/hooks/use-sector-performance"
import type { SectorPerformanceItem } from "@/lib/api"
import { SurfaceCard } from "./ui-kit"

const TOP_COUNT = 5

const percent = (value: number) =>
  `${value >= 0 ? "+" : "−"}${Math.abs(value).toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`

/** Sector market cap arrives in tỷ; anything past a thousand reads better scaled. */
function marketCap(value: number): string {
  if (value >= 1_000) {
    return `${(value / 1_000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })}N tỷ`
  }
  return `${value.toLocaleString("vi-VN", { maximumFractionDigits: 0 })} tỷ`
}

function SectorRow({
  sector,
  direction,
}: {
  sector: SectorPerformanceItem
  direction: "up" | "down"
}) {
  // Show the movers that made the sector move: gainers for a rising sector,
  // losers for a falling one. The other list would just be noise here.
  const picks = (direction === "up" ? sector.top_gainers : sector.top_losers).slice(0, 2)

  return (
    <div className="grid grid-cols-[1fr_auto] items-baseline gap-4 border-t border-hairline py-2.5">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-[0.95rem] font-semibold">
          {sector.icb_name}
        </span>
        <span className="text-meta text-muted-foreground">
          {marketCap(sector.total_market_cap)} · {sector.stock_count} CP
        </span>
      </div>
      <div className="flex flex-col items-end gap-0.5">
        <span
          className={cn(
            "text-[0.95rem] tabular-nums",
            direction === "up" ? "text-positive" : "text-negative"
          )}
        >
          {percent(sector.change_pct)}
        </span>
        {picks.length > 0 && (
          <span className="text-meta text-muted-foreground">
            {picks.join(", ")}
          </span>
        )}
      </div>
    </div>
  )
}

function SectorCard({
  title,
  sectors,
  direction,
  session,
}: {
  title: string
  sectors: SectorPerformanceItem[]
  direction: "up" | "down"
  session: string | null
}) {
  return (
    <SurfaceCard>
      <div className="flex flex-wrap items-baseline justify-between gap-4 pb-2">
        <span className="text-[1.05rem] font-semibold leading-[1.24]">
          {title}
        </span>
        {session && (
          <span className="text-meta text-muted-foreground">
            Phiên {session}
          </span>
        )}
      </div>
      {sectors.length === 0 ? (
        <p className="border-t border-hairline py-4 text-meta text-muted-foreground">
          Chưa có ngành nào {direction === "up" ? "tăng" : "giảm"} trong phiên này.
        </p>
      ) : (
        sectors.map((sector) => (
          <SectorRow key={sector.icb_code} sector={sector} direction={direction} />
        ))
      )}
    </SurfaceCard>
  )
}

/**
 * The two ends of the sector table, side by side. Ranking only the extremes is
 * the point: a reader scanning the market wants to know what led and what
 * dragged, not to page through thirty rows in the middle.
 */
export function SectorPerformanceSection({ className }: { className?: string }) {
  const { data, isPending } = useSectorPerformance()

  const sectors = data?.sectors ?? []
  const gainers = sectors
    .filter((s) => s.change_pct > 0)
    .sort((a, b) => b.change_pct - a.change_pct)
    .slice(0, TOP_COUNT)
  const losers = sectors
    .filter((s) => s.change_pct < 0)
    .sort((a, b) => a.change_pct - b.change_pct)
    .slice(0, TOP_COUNT)

  const session = data?.generated_at
    ? new Date(data.generated_at).toLocaleDateString("vi-VN")
    : null

  if (isPending) {
    return <SectorPerformanceSkeleton className={className} />
  }

  return (
    <>
      <SectorCard
        title="Top 5 ngành tăng"
        sectors={gainers}
        direction="up"
        session={session}
      />
      <SectorCard
        title="Top 5 ngành giảm"
        sectors={losers}
        direction="down"
        session={session}
      />
    </>
  )
}

function SectorPerformanceSkeleton({ className }: { className?: string }) {
  return (
    <>
      {[0, 1].map((i) => (
        <div
          key={i}
          className={cn(
            "h-[340px] animate-pulse rounded-card border border-border bg-card",
            className
          )}
        />
      ))}
    </>
  )
}

export { SectorPerformanceSkeleton }
