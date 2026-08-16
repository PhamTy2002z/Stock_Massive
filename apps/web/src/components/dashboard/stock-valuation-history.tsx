"use client"

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { Skeleton } from "@/components/ui/skeleton"
import { useValuationSeries } from "@/hooks/use-valuation-series"
import { CHART_GRID_PROPS, CHART_TOOLTIP_STYLE } from "@/lib/chart-theme"
import { formatDataAge } from "@/lib/format"
import { formatVietnamDate } from "@/lib/market-session"
import { cn } from "@/lib/utils"
import { SurfaceCard } from "./ui-kit"

/** A year of sessions: long enough to see a re-rating, short enough to read. */
const WINDOW_DAYS = 365

/** Recharts hands a tooltip value back untyped; anything but a number is a gap. */
const ratio = (value: unknown) =>
  typeof value === "number"
    ? value.toLocaleString("vi-VN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "—"

/** Day and month only: a year of sessions has no room for four-digit years. */
function tick(value: string): string {
  return formatVietnamDate(value).slice(0, 5)
}

/**
 * A symbol's own valuation history, which is the only fair thing to read it
 * against.
 *
 * P/E and P/B share a chart but not an axis: the two live on different scales,
 * and a shared one would flatten whichever is smaller into a straight line.
 * Renders nothing at all for a symbol the system does not collect — the panel
 * below already says so once, and saying it twice teaches the reader to skim.
 */
export function StockValuationHistory({
  symbol,
  className,
}: {
  symbol: string
  className?: string
}) {
  const { data } = useValuationSeries(symbol, WINDOW_DAYS)

  if (data === null || data.points.length < 2) return null

  const points = data.points.map((point) => ({
    session: point.effective_at,
    pe: point.provider_pe,
    pb: point.provider_pb,
  }))

  return (
    <SurfaceCard className={className}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-[1.05rem] font-semibold leading-[1.24]">
          Định giá theo thời gian
        </h2>
        <span className="text-meta text-muted-foreground">
          {data.points.length} phiên · {data.points[data.points.length - 1].source}
          {data.age_seconds !== null && ` · ${formatDataAge(data.age_seconds)} trước`}
          {data.stale && " · quá cũ"}
        </span>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={points} margin={{ top: 16, right: 8, left: -8, bottom: 0 }}>
          <CartesianGrid {...CHART_GRID_PROPS} />
          <XAxis
            dataKey="session"
            tickFormatter={tick}
            minTickGap={48}
            tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
          />
          <YAxis
            yAxisId="pe"
            width={44}
            tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
          />
          <YAxis
            yAxisId="pb"
            orientation="right"
            width={44}
            tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
          />
          {/* recharts types the tooltip label as ReactNode, not string — the
              value is our own date key, so it is narrowed rather than asserted. */}
          <Tooltip
            contentStyle={CHART_TOOLTIP_STYLE}
            labelFormatter={(label) =>
              typeof label === "string" ? `Phiên ${formatVietnamDate(label)}` : label
            }
            formatter={(value, name) => [ratio(value), String(name)]}
          />
          <Legend />
          <Line
            yAxisId="pe"
            type="monotone"
            dataKey="pe"
            name="P/E"
            stroke="hsl(var(--foreground))"
            dot={false}
            strokeWidth={2}
            connectNulls
          />
          <Line
            yAxisId="pb"
            type="monotone"
            dataKey="pb"
            name="P/B"
            stroke="hsl(var(--muted-foreground))"
            dot={false}
            strokeWidth={2}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </SurfaceCard>
  )
}

export function StockValuationHistorySkeleton({ className }: { className?: string }) {
  return (
    <SurfaceCard className={cn("space-y-3", className)}>
      <Skeleton className="h-5 w-52" />
      <Skeleton className="h-[240px] w-full" />
    </SurfaceCard>
  )
}
