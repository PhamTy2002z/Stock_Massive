"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { PriceDepthResponse, PriceLevel } from "@/lib/api"

interface PriceDepthWidgetProps {
  data: PriceDepthResponse | undefined
  isLoading: boolean
}

function formatPrice(value: number): string {
  return value.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatVolume(value: number): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`
  }
  return value.toLocaleString("vi-VN")
}

function PriceLevelRow({
  level,
  type,
  maxVolume,
}: {
  level: PriceLevel | null
  type: "bid" | "ask"
  maxVolume: number
}) {
  if (!level) return null

  const widthPercent = maxVolume > 0 ? (level.volume / maxVolume) * 100 : 0
  const bgColor = type === "bid" ? "bg-green-500/20" : "bg-red-500/20"

  return (
    <div className="relative flex justify-between items-center text-sm py-1.5 px-2">
      <div
        className={cn("absolute inset-0", bgColor)}
        style={{
          width: `${widthPercent}%`,
          [type === "bid" ? "right" : "left"]: 0,
          [type === "bid" ? "left" : "right"]: "auto",
        }}
      />
      <span className="relative z-10 font-medium tabular-nums">
        {formatPrice(level.price)}
      </span>
      <span className="relative z-10 text-muted-foreground tabular-nums">
        {formatVolume(level.volume)}
      </span>
    </div>
  )
}

export function PriceDepthWidget({ data, isLoading }: PriceDepthWidgetProps) {
  if (isLoading) {
    return <PriceDepthWidgetSkeleton />
  }

  if (!data) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        Không có dữ liệu price depth
      </div>
    )
  }

  const bidLevels = [data.bid_1, data.bid_2, data.bid_3].filter(Boolean) as PriceLevel[]
  const askLevels = [data.ask_1, data.ask_2, data.ask_3].filter(Boolean) as PriceLevel[]
  const allVolumes = [...bidLevels, ...askLevels].map((l) => l.volume)
  const maxVolume = Math.max(...allVolumes, 1)

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Bid Side */}
      <Card className="border-green-500/30">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-green-600 dark:text-green-400">
              BID
            </h4>
            <span className="text-xs text-muted-foreground">
              {formatVolume(data.total_bid_volume)}
            </span>
          </div>
          <div className="space-y-1">
            {bidLevels.map((level, i) => (
              <PriceLevelRow
                key={i}
                level={level}
                type="bid"
                maxVolume={maxVolume}
              />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Ask Side */}
      <Card className="border-red-500/30">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-red-600 dark:text-red-400">
              ASK
            </h4>
            <span className="text-xs text-muted-foreground">
              {formatVolume(data.total_ask_volume)}
            </span>
          </div>
          <div className="space-y-1">
            {askLevels.map((level, i) => (
              <PriceLevelRow
                key={i}
                level={level}
                type="ask"
                maxVolume={maxVolume}
              />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Spread Info */}
      <div className="col-span-2 flex items-center justify-center gap-4 py-2 text-sm">
        <span className="text-muted-foreground">Spread:</span>
        <span className="font-medium tabular-nums">
          {formatPrice(data.spread)}
        </span>
        <span
          className={cn(
            "text-xs px-2 py-0.5 rounded-full",
            data.spread_percent < 0.5
              ? "bg-green-500/20 text-green-600 dark:text-green-400"
              : data.spread_percent < 1
                ? "bg-yellow-500/20 text-yellow-600 dark:text-yellow-400"
                : "bg-red-500/20 text-red-600 dark:text-red-400"
          )}
        >
          {data.spread_percent.toFixed(2)}%
        </span>
      </div>
    </div>
  )
}

function PriceDepthWidgetSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <Card>
        <CardContent className="p-4 space-y-3">
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-4 space-y-3">
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
        </CardContent>
      </Card>
      <div className="col-span-2 flex justify-center">
        <Skeleton className="h-4 w-32" />
      </div>
    </div>
  )
}

export { PriceDepthWidgetSkeleton }
