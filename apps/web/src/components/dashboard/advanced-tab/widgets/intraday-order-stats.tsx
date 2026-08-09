"use client"

import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { formatVolume } from "@/lib/format"
import type { IntradayOrderStatsResponse } from "@/lib/api"
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Sunrise,
  Sunset,
} from "lucide-react"

interface IntradayOrderStatsProps {
  data: IntradayOrderStatsResponse | undefined
  isLoading: boolean
}

function formatNumber(value: number): string {
  return value.toLocaleString("vi-VN")
}

const COLORS = {
  buy: "hsl(142 76% 36%)",
  buyLight: "hsl(142 76% 45%)",
  sell: "hsl(0 84% 60%)",
  sellLight: "hsl(0 84% 65%)",
  ato: "hsl(38 92% 50%)",
  atc: "hsl(262 83% 58%)",
}

export function IntradayOrderStats({ data, isLoading }: IntradayOrderStatsProps) {
  if (isLoading) return <IntradayOrderStatsSkeleton />

  if (!data) {
    return (
      <div className="text-center py-12">
        <div className="w-14 h-14 mx-auto mb-3 rounded-2xl bg-muted/30 flex items-center justify-center">
          <Activity className="w-7 h-7 text-muted-foreground/40" />
        </div>
        <p className="text-sm font-medium text-muted-foreground">Dữ liệu intraday chưa khả dụng</p>
        <p className="text-xs text-muted-foreground/70 mt-1">Chỉ có trong giờ giao dịch</p>
      </div>
    )
  }

  const netVolume = data.buy_volume - data.sell_volume
  const totalVolume = data.buy_volume + data.sell_volume
  const buyPct = totalVolume > 0 ? (data.buy_volume / totalVolume) * 100 : 50

  return (
    <div className="space-y-4">
      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs">
          <span className="font-medium" style={{ color: COLORS.buy }}>
            Mua ({buyPct.toFixed(1)}%)
          </span>
          <span className="font-medium" style={{ color: COLORS.sell }}>
            Bán ({(100 - buyPct).toFixed(1)}%)
          </span>
        </div>
        <div className="h-3 rounded-full overflow-hidden flex bg-muted/30 shadow-inner">
          <div
            className="transition-all duration-500 ease-out"
            style={{
              width: `${buyPct}%`,
              background: `linear-gradient(90deg, ${COLORS.buy} 0%, ${COLORS.buyLight} 100%)`,
            }}
          />
          <div
            className="transition-all duration-500 ease-out"
            style={{
              width: `${100 - buyPct}%`,
              background: `linear-gradient(90deg, ${COLORS.sellLight} 0%, ${COLORS.sell} 100%)`,
            }}
          />
        </div>
      </div>

      {/* Buy/Sell Cards */}
      <div className="grid grid-cols-2 gap-3">
        <Card
          className="cursor-pointer transition-all duration-200 hover:scale-[1.02] hover:-translate-y-0.5 outline-none focus:outline-none"
          style={{
            borderColor: `${COLORS.buy}30`,
            background: `linear-gradient(135deg, ${COLORS.buy}08 0%, ${COLORS.buy}12 100%)`,
          }}
        >
          <CardContent className="p-3">
            <div className="flex items-center gap-2 mb-2">
              <div
                className="p-1.5 rounded-lg"
                style={{ backgroundColor: `${COLORS.buy}20` }}
              >
                <TrendingUp className="h-3.5 w-3.5" style={{ color: COLORS.buy }} />
              </div>
              <span className="text-xs font-semibold" style={{ color: COLORS.buy }}>Mua</span>
            </div>
            <p className="text-xl font-bold tabular-nums" style={{ color: COLORS.buy }}>
              {formatNumber(data.buy_orders)}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              lệnh • {formatVolume(data.buy_volume)} CP
            </p>
          </CardContent>
        </Card>

        <Card
          className="cursor-pointer transition-all duration-200 hover:scale-[1.02] hover:-translate-y-0.5 outline-none focus:outline-none"
          style={{
            borderColor: `${COLORS.sell}30`,
            background: `linear-gradient(135deg, ${COLORS.sell}08 0%, ${COLORS.sell}12 100%)`,
          }}
        >
          <CardContent className="p-3">
            <div className="flex items-center gap-2 mb-2">
              <div
                className="p-1.5 rounded-lg"
                style={{ backgroundColor: `${COLORS.sell}20` }}
              >
                <TrendingDown className="h-3.5 w-3.5" style={{ color: COLORS.sell }} />
              </div>
              <span className="text-xs font-semibold" style={{ color: COLORS.sell }}>Bán</span>
            </div>
            <p className="text-xl font-bold tabular-nums" style={{ color: COLORS.sell }}>
              {formatNumber(data.sell_orders)}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              lệnh • {formatVolume(data.sell_volume)} CP
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Net Volume */}
      <div
        className={cn(
          "p-4 rounded-xl text-center transition-all duration-200",
          netVolume > 0 && "bg-green-500/5 border border-green-500/20",
          netVolume < 0 && "bg-red-500/5 border border-red-500/20",
          netVolume === 0 && "bg-muted/30 border border-border/50"
        )}
      >
        <p className="text-sm text-muted-foreground mb-1">KL Ròng</p>
        <p
          className={cn(
            "text-2xl font-bold tabular-nums",
            netVolume > 0 ? "text-green-600" : netVolume < 0 ? "text-red-600" : "text-muted-foreground"
          )}
        >
          {netVolume > 0 ? "+" : ""}{formatVolume(netVolume)}
        </p>
        <div
          className={cn(
            "inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded-full text-xs font-medium",
            netVolume > 0 && "bg-green-500/20 text-green-600",
            netVolume < 0 && "bg-red-500/20 text-red-600",
            netVolume === 0 && "bg-muted/50 text-muted-foreground"
          )}
        >
          {netVolume > 0 ? (
            <>
              <TrendingUp className="h-3 w-3" />
              Lực mua ưu thế
            </>
          ) : netVolume < 0 ? (
            <>
              <TrendingDown className="h-3 w-3" />
              Lực bán ưu thế
            </>
          ) : (
            "Cân bằng"
          )}
        </div>
      </div>

      {/* ATO/ATC */}
      <div className="grid grid-cols-2 gap-3">
        <div
          className="p-3 rounded-xl text-center cursor-pointer transition-all duration-200 hover:scale-[1.02]"
          style={{
            backgroundColor: `${COLORS.ato}08`,
            border: `1px solid ${COLORS.ato}20`,
          }}
        >
          <div className="flex items-center justify-center gap-1.5 mb-1">
            <Sunrise className="h-3.5 w-3.5" style={{ color: COLORS.ato }} />
            <p className="text-xs text-muted-foreground">ATO</p>
          </div>
          <p className="text-lg font-bold tabular-nums" style={{ color: COLORS.ato }}>
            {formatVolume(data.ato_volume)}
          </p>
        </div>
        <div
          className="p-3 rounded-xl text-center cursor-pointer transition-all duration-200 hover:scale-[1.02]"
          style={{
            backgroundColor: `${COLORS.atc}08`,
            border: `1px solid ${COLORS.atc}20`,
          }}
        >
          <div className="flex items-center justify-center gap-1.5 mb-1">
            <Sunset className="h-3.5 w-3.5" style={{ color: COLORS.atc }} />
            <p className="text-xs text-muted-foreground">ATC</p>
          </div>
          <p className="text-lg font-bold tabular-nums" style={{ color: COLORS.atc }}>
            {formatVolume(data.atc_volume)}
          </p>
        </div>
      </div>

      {/* Session Info */}
      <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground pt-2">
        <div className="h-px flex-1 bg-border/50" />
        <span>
          {data.date
            ? new Date(data.date).toLocaleDateString("vi-VN", {
                weekday: "short",
                day: "2-digit",
                month: "2-digit",
              })
            : "Không có dữ liệu phiên"}
        </span>
        <span className="text-muted-foreground/50">•</span>
        <span>{new Date(data.last_updated).toLocaleTimeString("vi-VN")}</span>
        <div className="h-px flex-1 bg-border/50" />
      </div>
    </div>
  )
}

function IntradayOrderStatsSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-3 w-full rounded-full" />
      <div className="grid grid-cols-2 gap-3">
        <Skeleton className="h-24 rounded-xl" />
        <Skeleton className="h-24 rounded-xl" />
      </div>
      <Skeleton className="h-20 rounded-xl" />
      <div className="grid grid-cols-2 gap-3">
        <Skeleton className="h-16 rounded-xl" />
        <Skeleton className="h-16 rounded-xl" />
      </div>
    </div>
  )
}
