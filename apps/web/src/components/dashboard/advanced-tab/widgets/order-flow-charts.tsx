"use client"

import { useMemo } from "react"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  Cell,
} from "recharts"
// Card/CardContent removed - using custom dark styled divs
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { formatVolume } from "@/lib/format"
import type { IntradayOrderStatsResponse } from "@/lib/api"
import {
  TrendingUp,
  TrendingDown,
  Activity,
  ArrowUpDown,
  Sunrise,
  Sunset,
} from "lucide-react"

interface OrderFlowChartsProps {
  data: IntradayOrderStatsResponse | undefined
  isLoading: boolean
}

// Design pattern: Muted Green/Red - Bloomberg/FireAnt/TradingView style
const COLORS = {
  // Buy side - Muted emerald (professional trading UI)
  buy: "hsl(158 40% 45%)",        // Muted emerald-green
  buyLight: "hsl(158 35% 52%)",   // Lighter variant
  // Sell side - Muted rose (low saturation for dark mode)
  sell: "hsl(0 45% 50%)",         // Muted rose-red
  sellLight: "hsl(0 40% 58%)",    // Lighter variant
  // Session markers - Neutral tones
  ato: "hsl(35 50% 55%)",         // Muted amber
  atc: "hsl(220 12% 55%)",        // Slate grey
  // Neutral
  neutral: "hsl(0 0% 45%)",
  // Card styling - elevated dark
  cardBg: "hsl(0 0% 13%)",        // Darker base
  cardBorder: "hsl(0 0% 20%)",    // Softer border
  cardElevated: "hsl(0 0% 15%)",  // Elevated card
  // Text colors - readable
  textMuted: "hsl(0 0% 60%)",     // Labels - readable
  textDim: "hsl(0 0% 50%)",       // Secondary info
}

function formatNumber(value: number): string {
  return value.toLocaleString("vi-VN")
}


// Radial progress ring component - Monochrome design
function RadialProgress({
  value,
  label,
  color,
  secondaryLabel,
  size = "md"
}: {
  value: number
  label: string
  color: string
  secondaryLabel?: string
  size?: "sm" | "md" | "lg"
}) {
  const percentage = Math.min(Math.max(value, 0), 100)
  const circumference = 2 * Math.PI * 40
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  const sizeClasses = {
    sm: "w-20 h-20",
    md: "w-28 h-28",
    lg: "w-32 h-32",
  }

  const textSizes = {
    sm: "text-base",
    md: "text-xl",
    lg: "text-2xl",
  }

  return (
    <div className={cn("relative", sizeClasses[size])}>
      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
        {/* Background ring - subtle grey */}
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="none"
          stroke="hsl(0 0% 30%)"
          strokeWidth="6"
        />
        {/* Progress ring */}
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-700 ease-out"
          style={{ filter: `drop-shadow(0 0 8px ${color}50)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={cn("font-bold tabular-nums", textSizes[size])}
          style={{ color }}
        >
          {percentage.toFixed(1)}%
        </span>
        <span className="text-[10px] font-medium" style={{ color: COLORS.textMuted }}>{label}</span>
        {secondaryLabel && (
          <span className="text-[9px]" style={{ color: COLORS.textDim }}>{secondaryLabel}</span>
        )}
      </div>
    </div>
  )
}

// Stats card - Bloomberg/TradingView style with elevation
function StatsCard({
  icon: Icon,
  label,
  value,
  subValue,
  color,
  percentage,
  percentageLabel,
}: {
  icon: React.ElementType
  label: string
  value: string
  subValue?: string
  color: string
  percentage?: number
  percentageLabel?: string
}) {
  return (
    <div
      className="group relative overflow-hidden rounded-xl p-4 transition-all duration-200 hover:translate-y-[-2px]"
      style={{
        backgroundColor: COLORS.cardElevated,
        border: `1px solid ${COLORS.cardBorder}`,
        boxShadow: "0 4px 12px rgba(0,0,0,0.3), 0 1px 3px rgba(0,0,0,0.2)",
      }}
    >
      {/* Accent line on top */}
      <div
        className="absolute top-0 left-0 right-0 h-0.5 opacity-80"
        style={{ backgroundColor: color }}
      />

      <div className="flex items-start justify-between mb-3">
        <div
          className="p-2 rounded-lg transition-transform duration-200 group-hover:scale-110"
          style={{ backgroundColor: `${color}12` }}
        >
          <Icon className="h-4 w-4" style={{ color }} />
        </div>
        {percentage !== undefined && (
          <span
            className="text-xs font-medium tabular-nums"
            style={{ color: COLORS.textMuted }}
          >
            {percentage.toFixed(1)}%
          </span>
        )}
      </div>

      <p className="text-2xl font-bold tabular-nums mb-1" style={{ color }}>
        {value}
      </p>
      <p className="text-xs" style={{ color: COLORS.textMuted }}>
        {label}
        {subValue && <span className="ml-1" style={{ color: COLORS.textDim }}>• {subValue}</span>}
      </p>

      {percentageLabel && (
        <div className="mt-3 pt-3" style={{ borderTop: "1px solid hsl(0 0% 22%)" }}>
          <div className="flex justify-between items-center text-xs">
            <span style={{ color: COLORS.textDim }}>{percentageLabel}</span>
            <span className="font-semibold tabular-nums" style={{ color }}>
              {percentage?.toFixed(1)}%
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

// Mini stat card for ATO/ATC - Elevated dark theme
function MiniStatCard({
  icon: Icon,
  label,
  value,
  color,
  description,
}: {
  icon: React.ElementType
  label: string
  value: string
  color: string
  description: string
}) {
  return (
    <div
      className="group flex items-center gap-4 p-4 rounded-xl transition-all duration-200 hover:translate-y-[-2px]"
      style={{
        backgroundColor: COLORS.cardBg,
        border: `1px solid ${COLORS.cardBorder}`,
        boxShadow: "0 2px 8px rgba(0,0,0,0.25)",
      }}
    >
      <div
        className="p-2.5 rounded-lg transition-transform duration-200 group-hover:scale-110"
        style={{ backgroundColor: `${color}12` }}
      >
        <Icon className="h-5 w-5" style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs mb-0.5" style={{ color: COLORS.textMuted }}>{label}</p>
        <p className="text-xl font-bold tabular-nums" style={{ color }}>{value}</p>
        <p className="text-[10px] mt-0.5" style={{ color: COLORS.textDim }}>{description}</p>
      </div>
    </div>
  )
}

export function OrderFlowCharts({ data, isLoading }: OrderFlowChartsProps) {
  // Compute derived data first (before any returns) to satisfy hooks rules
  const volumeBarData = useMemo(() => {
    if (!data) return []
    return [
      { name: "Mua", value: data.buy_volume, fill: COLORS.buy },
      { name: "Bán", value: data.sell_volume, fill: COLORS.sell },
    ]
  }, [data])

  if (isLoading) return <OrderFlowChartsSkeleton />

  if (!data) {
    return (
      <div className="text-center py-16">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-muted/30 flex items-center justify-center">
          <Activity className="w-8 h-8 text-muted-foreground/40" />
        </div>
        <p className="text-sm font-medium text-muted-foreground">Dữ liệu intraday chưa khả dụng</p>
        <p className="text-xs text-muted-foreground/70 mt-1">Chỉ có trong giờ giao dịch</p>
      </div>
    )
  }

  const netVolume = data.buy_volume - data.sell_volume
  const totalOrders = data.buy_orders + data.sell_orders
  const totalVolume = data.buy_volume + data.sell_volume
  const buyOrderPct = totalOrders > 0 ? (data.buy_orders / totalOrders) * 100 : 50
  const buyVolumePct = totalVolume > 0 ? (data.buy_volume / totalVolume) * 100 : 50

  return (
    <div className="space-y-6">
      {/* Section 1: Radial Charts + Buy/Sell Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Radial Charts - Elevated dark theme */}
        <div
          className="lg:col-span-2 rounded-xl p-5"
          style={{
            backgroundColor: COLORS.cardElevated,
            border: `1px solid ${COLORS.cardBorder}`,
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
          }}
        >
          <h4 className="text-sm font-semibold mb-4 flex items-center gap-2 text-white">
            <Activity className="h-4 w-4" style={{ color: COLORS.buy }} />
            Tỷ lệ Mua/Bán
          </h4>
          <div className="flex justify-around items-center py-2">
            <RadialProgress
              value={buyOrderPct}
              label="Lệnh mua"
              secondaryLabel={`${formatNumber(data.buy_orders)} lệnh`}
              color={COLORS.buy}
              size="md"
            />
            <div className="flex flex-col items-center gap-1">
              <ArrowUpDown className="h-5 w-5 text-white/30" />
              <span className="text-xs text-white/40">vs</span>
            </div>
            <RadialProgress
              value={buyVolumePct}
              label="KL mua"
              secondaryLabel={formatVolume(data.buy_volume)}
              color={COLORS.buyLight}
              size="md"
            />
          </div>
          {/* Legend */}
          <div className="flex justify-center gap-6 mt-4 pt-3" style={{ borderTop: `1px solid ${COLORS.cardBorder}` }}>
            <div className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: COLORS.buy }}
              />
              <span className="text-xs" style={{ color: COLORS.textMuted }}>% Lệnh Mua</span>
            </div>
            <div className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: COLORS.buyLight }}
              />
              <span className="text-xs" style={{ color: COLORS.textMuted }}>% KL Mua</span>
            </div>
          </div>
        </div>

        {/* Buy/Sell Stats Cards */}
        <div className="lg:col-span-3 grid grid-cols-2 gap-4">
          <StatsCard
            icon={TrendingUp}
            label="lệnh mua"
            value={formatNumber(data.buy_orders)}
            subValue={`${formatVolume(data.buy_volume)} CP`}
            color={COLORS.buy}
            percentage={buyOrderPct}
            percentageLabel="% Tổng lệnh"
          />
          <StatsCard
            icon={TrendingDown}
            label="lệnh bán"
            value={formatNumber(data.sell_orders)}
            subValue={`${formatVolume(data.sell_volume)} CP`}
            color={COLORS.sell}
            percentage={100 - buyOrderPct}
            percentageLabel="% Tổng lệnh"
          />
        </div>
      </div>

      {/* Section 2: Volume Comparison Bar Chart - Elevated dark theme */}
      <div
        className="rounded-xl p-5"
        style={{
          backgroundColor: COLORS.cardElevated,
          border: `1px solid ${COLORS.cardBorder}`,
          boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
        }}
      >
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-sm font-semibold text-white">So sánh Khối lượng</h4>
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-full"
            style={{ backgroundColor: COLORS.cardBorder }}
          >
            <span className="text-xs" style={{ color: COLORS.textDim }}>KL Ròng:</span>
            <span
              className="text-sm font-bold tabular-nums"
              style={{ color: netVolume >= 0 ? COLORS.buy : COLORS.sell }}
            >
              {netVolume > 0 ? "+" : ""}{formatVolume(netVolume)}
            </span>
          </div>
        </div>

        {/* Bar Chart */}
        <div className="h-24 mb-4">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={volumeBarData} layout="vertical" barCategoryGap="30%">
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                width={36}
                tick={{ fontSize: 12, fontWeight: 500, fill: "hsl(0 0% 70%)" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: COLORS.cardBorder }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const d = payload[0].payload
                  return (
                    <div
                      className="rounded-lg px-3 py-2"
                      style={{
                        backgroundColor: COLORS.cardBg,
                        border: `1px solid ${COLORS.cardBorder}`,
                        boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
                      }}
                    >
                      <p className="text-sm font-semibold text-white">{d.name}</p>
                      <p className="text-xs mt-0.5" style={{ color: COLORS.textMuted }}>
                        {formatVolume(d.value)} cổ phiếu
                      </p>
                    </div>
                  )
                }}
              />
              <Bar
                dataKey="value"
                radius={[0, 6, 6, 0]}
                className="transition-all duration-200"
              >
                {volumeBarData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.fill}
                    className="hover:opacity-80 transition-opacity duration-200"
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs">
            <span className="font-medium" style={{ color: COLORS.buy }}>
              Mua: {buyVolumePct.toFixed(1)}%
            </span>
            <span className="font-medium" style={{ color: COLORS.sell }}>
              Bán: {(100 - buyVolumePct).toFixed(1)}%
            </span>
          </div>
          <div
            className="h-2.5 rounded-full overflow-hidden flex"
            style={{ backgroundColor: COLORS.cardBorder }}
          >
            <div
              className="transition-all duration-500 ease-out"
              style={{
                width: `${buyVolumePct}%`,
                background: `linear-gradient(90deg, ${COLORS.buy} 0%, ${COLORS.buyLight} 100%)`,
              }}
            />
            <div
              className="transition-all duration-500 ease-out"
              style={{
                width: `${100 - buyVolumePct}%`,
                background: `linear-gradient(90deg, ${COLORS.sellLight} 0%, ${COLORS.sell} 100%)`,
              }}
            />
          </div>
        </div>
      </div>

      {/* Section 3: Net Volume + ATO/ATC */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Net Volume - Elevated dark theme */}
        <div
          className="md:col-span-1 rounded-xl p-5 text-center relative overflow-hidden"
          style={{
            backgroundColor: COLORS.cardBg,
            border: `1px solid ${COLORS.cardBorder}`,
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
          }}
        >
          {/* Accent glow */}
          <div
            className="absolute inset-0 opacity-5"
            style={{
              background: `radial-gradient(circle at center, ${netVolume >= 0 ? COLORS.buy : COLORS.sell} 0%, transparent 70%)`,
            }}
          />

          <p className="text-sm mb-3 relative" style={{ color: COLORS.textMuted }}>Khối lượng Ròng</p>
          <p
            className="text-4xl font-bold tabular-nums mb-2 relative"
            style={{ color: netVolume >= 0 ? COLORS.buy : COLORS.sell }}
          >
            {netVolume > 0 ? "+" : ""}{formatVolume(netVolume)}
          </p>
          <div
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium relative"
            style={{
              backgroundColor: `${netVolume >= 0 ? COLORS.buy : COLORS.sell}20`,
              color: netVolume >= 0 ? COLORS.buy : COLORS.sell,
            }}
          >
            {netVolume >= 0 ? (
              <>
                <TrendingUp className="h-3 w-3" />
                Lực mua chiếm ưu thế
              </>
            ) : (
              <>
                <TrendingDown className="h-3 w-3" />
                Lực bán chiếm ưu thế
              </>
            )}
          </div>
        </div>

        {/* ATO/ATC Cards */}
        <div className="md:col-span-2 grid grid-cols-2 gap-4">
          <MiniStatCard
            icon={Sunrise}
            label="Phiên ATO"
            value={formatVolume(data.ato_volume)}
            color={COLORS.ato}
            description="Khối lượng mở cửa"
          />
          <MiniStatCard
            icon={Sunset}
            label="Phiên ATC"
            value={formatVolume(data.atc_volume)}
            color={COLORS.atc}
            description="Khối lượng đóng cửa"
          />
        </div>
      </div>

      {/* Session Footer - Muted */}
      <div className="flex items-center justify-center gap-2 text-xs" style={{ color: COLORS.textDim }}>
        <div className="h-px flex-1" style={{ backgroundColor: COLORS.cardBorder }} />
        <span>
          Phiên {new Date(data.date).toLocaleDateString("vi-VN", {
            weekday: "long",
            day: "2-digit",
            month: "2-digit",
            year: "numeric"
          })}
        </span>
        <span style={{ color: COLORS.cardBorder }}>•</span>
        <span>Cập nhật: {new Date(data.last_updated).toLocaleTimeString("vi-VN")}</span>
        <div className="h-px flex-1" style={{ backgroundColor: COLORS.cardBorder }} />
      </div>
    </div>
  )
}

function OrderFlowChartsSkeleton() {
  return (
    <div className="space-y-6">
      {/* Section 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <Skeleton className="lg:col-span-2 h-[200px] rounded-xl" />
        <div className="lg:col-span-3 grid grid-cols-2 gap-4">
          <Skeleton className="h-[180px] rounded-xl" />
          <Skeleton className="h-[180px] rounded-xl" />
        </div>
      </div>
      {/* Section 2 */}
      <Skeleton className="h-[180px] rounded-xl" />
      {/* Section 3 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Skeleton className="h-[140px] rounded-xl" />
        <div className="md:col-span-2 grid grid-cols-2 gap-4">
          <Skeleton className="h-[100px] rounded-xl" />
          <Skeleton className="h-[100px] rounded-xl" />
        </div>
      </div>
    </div>
  )
}
