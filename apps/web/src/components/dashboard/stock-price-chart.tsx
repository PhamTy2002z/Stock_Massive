"use client"

import { useId, useState } from "react"
import { usePriceHistory, type PriceRange } from "@/hooks/use-price-history"
import type { StockPricePoint } from "@/lib/api"
import { cn } from "@/lib/utils"

interface StockPriceChartProps {
  symbol: string
  /** Reference price for the session, drawn as the dashed baseline. */
  refPrice?: number | null
  className?: string
}

const ranges: PriceRange[] = ["1D", "5D", "1M", "6M", "1N", "5N"]

const VIEW_W = 800
const VIEW_H = 200
const VOL_H = 40

/** A short series must not turn into a few slabs the width of the card. */
const MAX_BAR_W = 16

/** Six evenly spaced ticks across the series, first and last included. */
function axisLabels(points: StockPricePoint[]): string[] {
  if (points.length === 0) return []
  const count = Math.min(6, points.length)
  const step = (points.length - 1) / Math.max(1, count - 1)

  // Intraday points carry a time component; daily ones do not. The axis follows
  // whichever the series actually is rather than a prop that could disagree.
  const isIntraday = points[0].time.includes("T")

  return Array.from({ length: count }, (_, i) => {
    const point = points[Math.round(i * step)]
    if (isIntraday) {
      const date = new Date(point.time)
      return date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })
    }
    const [year, month, day] = point.time.slice(0, 10).split("-")
    return `${day}/${month}${points.length > 200 ? `/${year.slice(2)}` : ""}`
  })
}

function Chip({
  label,
  isActive,
  onClick,
}: {
  label: string
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isActive}
      className={cn(
        "rounded-full px-[13px] py-1.5 text-[13px] leading-[1.29] tracking-[-0.208px]",
        "transition-transform duration-150 active:scale-95",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isActive
          ? "border-2 border-interactive-strong px-3 py-[5px] font-medium"
          : "border border-border hover:bg-muted"
      )}
    >
      {label}
    </button>
  )
}

function Frame({
  range,
  onRangeChange,
  children,
  className,
}: {
  range: PriceRange
  onRangeChange: (range: PriceRange) => void
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("min-w-0 rounded-[18px] border border-border bg-card p-[18px]", className)}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <span className="text-[13px] font-semibold leading-[1.29] tracking-[-0.208px] text-muted-foreground">
          Diễn biến giá
        </span>
        <div className="flex gap-1.5">
          {ranges.map((r) => (
            <Chip
              key={r}
              label={r}
              isActive={r === range}
              onClick={() => onRangeChange(r)}
            />
          ))}
        </div>
      </div>
      {children}
    </div>
  )
}

function Message({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-[220px] items-center justify-center text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
      {children}
    </div>
  )
}

/**
 * Price over the chosen range, drawn as a filled line with the volume of each
 * bar underneath. Plain SVG on a fixed viewBox rather than a charting library:
 * the shape is simple, and a `preserveAspectRatio` stretch re-renders nothing
 * when the sidebar expands beside it.
 */
export function StockPriceChart({ symbol, refPrice, className }: StockPriceChartProps) {
  const [range, setRange] = useState<PriceRange>("1D")
  const { data, isLoading, isError, error } = usePriceHistory(symbol, range)
  // Two charts on one page would otherwise share a mask and blank each other.
  // The colons React generates are not safe inside url(#…).
  const maskId = `price-reveal-${useId().replace(/:/g, "")}`

  if (isLoading) {
    return (
      <Frame range={range} onRangeChange={setRange} className={className}>
        <div className="mt-3.5 h-[220px] animate-pulse rounded-xl bg-muted" />
      </Frame>
    )
  }

  if (isError) {
    return (
      <Frame range={range} onRangeChange={setRange} className={className}>
        <Message>
          {error instanceof Error ? error.message : "Không tải được dữ liệu giá."}
        </Message>
      </Frame>
    )
  }

  const points = data ?? []
  if (points.length < 2) {
    return (
      <Frame range={range} onRangeChange={setRange} className={className}>
        <Message>Chưa đủ dữ liệu giá cho khoảng {range}.</Message>
      </Frame>
    )
  }

  const closes = points.map((p) => p.close)
  // The baseline joins the price scale, so the dashed line can never sit outside
  // the plotted area and read as if the price never touched it.
  const scaleValues = refPrice ? [...closes, refPrice] : closes
  const min = Math.min(...scaleValues)
  const max = Math.max(...scaleValues)
  const span = max - min || 1

  const x = (i: number) => (i / (points.length - 1)) * VIEW_W
  const y = (value: number) => VIEW_H - ((value - min) / span) * VIEW_H

  const line = points
    .map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.close).toFixed(1)}`)
    .join(" ")
  const area = `${line} L${VIEW_W} ${VIEW_H} L0 ${VIEW_H} Z`

  const isUp = closes[closes.length - 1] >= closes[0]
  const stroke = isUp ? "hsl(var(--positive))" : "hsl(var(--negative))"
  const fill = isUp ? "hsl(var(--positive) / 0.08)" : "hsl(var(--negative) / 0.08)"

  const maxVolume = Math.max(...points.map((p) => p.volume), 1)
  const barWidth = Math.min(MAX_BAR_W, Math.max(1, (VIEW_W / points.length) * 0.7))
  // Intraday buckets are minutes; every other range is one bar per session.
  const volumeLabel = range === "1D" ? "Khối lượng theo phút" : "Khối lượng theo phiên"

  return (
    <Frame range={range} onRangeChange={setRange} className={className}>
      <div className="relative mt-3.5">
        <svg
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`Biểu đồ giá ${symbol} khoảng ${range}`}
          className="block h-[220px] w-full"
        >
          <path
            d="M0 40H800M0 80H800M0 120H800M0 160H800"
            stroke="hsl(var(--hairline))"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
          {/* The reference line is stroked through a class rather than the
              attribute: a CSS property can carry a var() and so can follow the
              theme. Light keeps the lighter yellow it already shipped; dark
              takes the token that clears the tile. */}
          {refPrice !== null && refPrice !== undefined && (
            <path
              d={`M0 ${y(refPrice).toFixed(1)}H${VIEW_W}`}
              className="stroke-[#c99a00] dark:stroke-reference"
              strokeWidth="1"
              strokeDasharray="4 4"
              vectorEffect="non-scaling-stroke"
            />
          )}
          <defs>
            <mask id={maskId}>
              <rect
                key={range}
                x="0"
                y="-10"
                width={VIEW_W}
                height={VIEW_H + 20}
                fill="#fff"
                className="price-line-reveal"
              />
            </mask>
          </defs>
          <g mask={`url(#${maskId})`}>
            <path d={area} fill={fill} />
            <path
              d={line}
              fill="none"
              stroke={stroke}
              strokeWidth="1.75"
              strokeLinejoin="round"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
          </g>
        </svg>
        {refPrice !== null && refPrice !== undefined && (
          <span
            style={{ top: `${(y(refPrice) / VIEW_H) * 220 - 10}px` }}
            className="absolute right-0 rounded-full border border-[hsl(var(--hairline))] bg-card px-2 py-0.5 text-[11px] leading-[1.3] tracking-[-0.11px] tabular-nums text-reference"
          >
            TC {Math.round(refPrice).toLocaleString("vi-VN")}
          </span>
        )}
      </div>

      <div className="mt-1 flex justify-between text-[11px] leading-[1.3] tracking-[-0.11px] tabular-nums text-muted-foreground">
        {axisLabels(points).map((label, i) => (
          <span key={`${label}-${i}`}>{label}</span>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2.5 border-t border-[hsl(var(--hairline))] pt-3">
        <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
          {volumeLabel}
        </span>
        <svg
          viewBox={`0 0 ${VIEW_W} ${VOL_H}`}
          preserveAspectRatio="none"
          aria-hidden
          className="block h-[34px] min-w-[200px] flex-1"
        >
          {points.map((p, i) => {
            const height = Math.max(1, (p.volume / maxVolume) * VOL_H)
            // Green when the bar closed at or above its open — the same
            // up/down reading as the price line above it.
            const barFill =
              p.close >= p.open ? "hsl(var(--positive))" : "hsl(var(--negative))"
            return (
              <rect
                key={p.time}
                x={x(i) - barWidth / 2}
                y={VOL_H - height}
                width={barWidth}
                height={height}
                rx="1"
                fill={barFill}
              />
            )
          })}
        </svg>
      </div>
    </Frame>
  )
}

export function StockPriceChartSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-[360px] min-w-0 animate-pulse rounded-[18px] border border-border bg-card",
        className
      )}
    />
  )
}
