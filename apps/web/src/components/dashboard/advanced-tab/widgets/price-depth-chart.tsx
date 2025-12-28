"use client"

import { useMemo } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { PriceDepthResponse, PriceLevel } from "@/lib/api"

interface PriceDepthChartProps {
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
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
  return value.toLocaleString("vi-VN")
}

interface DepthBarProps {
  level: PriceLevel
  type: "bid" | "ask"
  maxVolume: number
  rank: number
}

function DepthBar({ level, type, maxVolume, rank }: DepthBarProps) {
  const widthPercent = maxVolume > 0 ? (level.volume / maxVolume) * 100 : 0
  const isBid = type === "bid"

  return (
    <div className={cn(
      "flex items-center gap-2 py-2 px-3 rounded-lg transition-colors cursor-pointer",
      "hover:bg-muted/50"
    )}>
      {/* Rank badge */}
      <span className={cn(
        "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0",
        isBid ? "bg-green-500/20 text-green-600" : "bg-red-500/20 text-red-600"
      )}>
        {rank}
      </span>

      {/* Price */}
      <span className={cn(
        "w-20 text-sm font-semibold tabular-nums",
        isBid ? "text-green-600" : "text-red-600"
      )}>
        {formatPrice(level.price)}
      </span>

      {/* Volume bar container */}
      <div className="flex-1 h-6 relative">
        <div
          className={cn(
            "absolute inset-y-0 rounded transition-all duration-300",
            isBid ? "bg-green-500/30 right-0" : "bg-red-500/30 left-0"
          )}
          style={{ width: `${widthPercent}%` }}
        />
        {/* Volume label */}
        <span className={cn(
          "absolute inset-y-0 flex items-center text-xs tabular-nums",
          isBid ? "right-2" : "left-2"
        )}>
          {formatVolume(level.volume)}
        </span>
      </div>
    </div>
  )
}

export function PriceDepthChart({ data, isLoading }: PriceDepthChartProps) {
  if (isLoading) return <PriceDepthChartSkeleton />

  if (!data) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        Không có dữ liệu price depth
      </div>
    )
  }

  // Check if market is closed
  const hasNoData = data.total_bid_volume === 0 && data.total_ask_volume === 0 &&
    data.bid_1?.price === 0 && data.ask_1?.price === 0

  if (hasNoData) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted/50 flex items-center justify-center">
          <svg className="w-8 h-8 text-muted-foreground/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <p className="text-sm font-medium">Không có dữ liệu sổ lệnh</p>
        <p className="text-xs mt-1 opacity-70">Chỉ khả dụng trong giờ giao dịch</p>
      </div>
    )
  }

  const bidLevels = useMemo(() =>
    [data.bid_1, data.bid_2, data.bid_3].filter(Boolean) as PriceLevel[],
    [data.bid_1, data.bid_2, data.bid_3]
  )
  const askLevels = useMemo(() =>
    [data.ask_1, data.ask_2, data.ask_3].filter(Boolean) as PriceLevel[],
    [data.ask_1, data.ask_2, data.ask_3]
  )

  const allVolumes = [...bidLevels, ...askLevels].map((l) => l.volume)
  const maxVolume = Math.max(...allVolumes, 1)
  const totalBidVolume = data.total_bid_volume
  const totalAskVolume = data.total_ask_volume
  const totalVolume = totalBidVolume + totalAskVolume
  const bidPct = totalVolume > 0 ? (totalBidVolume / totalVolume) * 100 : 50

  return (
    <div className="space-y-4">
      {/* Summary header */}
      <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-green-500" />
            <span className="text-sm">BID: <strong className="text-green-600">{formatVolume(totalBidVolume)}</strong></span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-red-500" />
            <span className="text-sm">ASK: <strong className="text-red-600">{formatVolume(totalAskVolume)}</strong></span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Spread:</span>
          <span className="text-sm font-semibold tabular-nums">{formatPrice(data.spread)}</span>
          <span className={cn(
            "text-xs px-2 py-0.5 rounded-full font-medium",
            data.spread_percent < 0.5
              ? "bg-green-500/20 text-green-600"
              : data.spread_percent < 1
                ? "bg-amber-500/20 text-amber-600"
                : "bg-red-500/20 text-red-600"
          )}>
            {data.spread_percent.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* Bid/Ask ratio bar */}
      <div>
        <div className="flex justify-between text-xs text-muted-foreground mb-1">
          <span>Mua ({bidPct.toFixed(1)}%)</span>
          <span>Bán ({(100 - bidPct).toFixed(1)}%)</span>
        </div>
        <div className="h-2 rounded-full overflow-hidden flex bg-muted/30">
          <div className="bg-green-500 transition-all duration-300" style={{ width: `${bidPct}%` }} />
          <div className="bg-red-500 transition-all duration-300" style={{ width: `${100 - bidPct}%` }} />
        </div>
      </div>

      {/* Depth levels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* BID Side */}
        <Card className="border-green-500/30 outline-none focus:outline-none">
          <CardContent className="p-3">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-bold text-green-600">BID (Mua)</h4>
              <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-600">
                {formatVolume(totalBidVolume)}
              </span>
            </div>
            <div className="space-y-1">
              {bidLevels.map((level, i) => (
                <DepthBar key={i} level={level} type="bid" maxVolume={maxVolume} rank={i + 1} />
              ))}
            </div>
          </CardContent>
        </Card>

        {/* ASK Side */}
        <Card className="border-red-500/30 outline-none focus:outline-none">
          <CardContent className="p-3">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-bold text-red-600">ASK (Bán)</h4>
              <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-600">
                {formatVolume(totalAskVolume)}
              </span>
            </div>
            <div className="space-y-1">
              {askLevels.map((level, i) => (
                <DepthBar key={i} level={level} type="ask" maxVolume={maxVolume} rank={i + 1} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pressure indicator */}
      <Card className={cn(
        "outline-none focus:outline-none",
        bidPct > 55 ? "border-green-500/30 bg-green-500/5" :
        bidPct < 45 ? "border-red-500/30 bg-red-500/5" : ""
      )}>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Áp lực thị trường</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Dựa trên tổng khối lượng đặt mua/bán
              </p>
            </div>
            <div className="text-right">
              <p className={cn(
                "text-lg font-bold",
                bidPct > 55 ? "text-green-600" :
                bidPct < 45 ? "text-red-600" : "text-muted-foreground"
              )}>
                {bidPct > 55 ? "MUA" : bidPct < 45 ? "BÁN" : "CÂN BẰNG"}
              </p>
              <p className="text-xs text-muted-foreground">
                {Math.abs(bidPct - 50).toFixed(1)}% {bidPct > 50 ? "nghiêng mua" : bidPct < 50 ? "nghiêng bán" : ""}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function PriceDepthChartSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-2 w-full rounded-full" />
      <div className="grid grid-cols-2 gap-4">
        <Skeleton className="h-[200px]" />
        <Skeleton className="h-[200px]" />
      </div>
      <Skeleton className="h-20" />
    </div>
  )
}

export { PriceDepthChartSkeleton }
