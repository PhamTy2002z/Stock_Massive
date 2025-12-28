"use client"

import { useMemo } from "react"
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from "recharts"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { ForeignSnapshotResponse } from "@/lib/api"
import { Globe, Users, TrendingUp, Percent, BarChart3, ArrowUpRight, ArrowDownRight } from "lucide-react"

interface ForeignFlowChartsProps {
  data: ForeignSnapshotResponse | undefined
  isLoading: boolean
}

// Color palette: Orange primary accent + muted semantic colors
const COLORS = {
  // Primary accent - Muted Orange (foreign/highlight)
  orange: "hsl(25 80% 55%)",        // Muted orange
  orangeLight: "hsl(25 70% 62%)",   // Lighter orange
  orangeDim: "hsla(25 80% 55% / 0.15)",
  // Neutral - Grey (domestic/secondary)
  grey: "#6B7280",
  greyLight: "#9CA3AF",
  greyDark: "#374151",
  // Semantic - Muted Green/Red for trends (dark mode friendly)
  up: "hsl(152 45% 50%)",           // Muted teal-green
  down: "hsl(4 55% 55%)",           // Muted coral-red
  // White
  white: "#FFFFFF",
  muted: "rgba(255, 255, 255, 0.6)",
}

function formatVolume(value: number): string {
  if (value >= 1000000000) return `${(value / 1000000000).toFixed(2)} tỷ`
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
  return value.toLocaleString("vi-VN")
}

function formatPct(value: number | null): string {
  if (value === null) return "N/A"
  return `${(value * 100).toFixed(2)}%`
}

// Radial progress with orange accent
function RadialProgress({ value, label, sublabel }: { value: number; label: string; sublabel?: string }) {
  const percentage = Math.min(Math.max(value * 100, 0), 100)
  const circumference = 2 * Math.PI * 40
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-28 h-28">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
          {/* Background circle */}
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke="currentColor"
            strokeWidth="6"
            className="text-muted/20"
          />
          {/* Progress circle with orange */}
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke={COLORS.orange}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-700 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-foreground">{percentage.toFixed(1)}%</span>
        </div>
      </div>
      <div className="text-center">
        <span className="text-sm font-medium text-foreground">{label}</span>
        {sublabel && <p className="text-xs text-muted-foreground">{sublabel}</p>}
      </div>
    </div>
  )
}

// Stat item component
function StatItem({
  icon: Icon,
  label,
  value,
  highlight = false,
  trend
}: {
  icon: React.ElementType
  label: string
  value: string
  highlight?: boolean
  trend?: "up" | "down" | null
}) {
  return (
    <div className={cn(
      "flex items-center gap-3 p-3 rounded-lg transition-colors",
      highlight ? "bg-primary/10 border border-primary/30" : "bg-muted/30"
    )}>
      <div className={cn(
        "w-9 h-9 rounded-lg flex items-center justify-center shrink-0",
        highlight ? "bg-primary/20" : "bg-muted/50"
      )}>
        <Icon className={cn("h-4 w-4", highlight ? "text-primary" : "text-muted-foreground")} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground truncate">{label}</p>
        <div className="flex items-center gap-1.5">
          <p className={cn(
            "text-sm font-semibold truncate",
            highlight ? "text-primary" : "text-foreground"
          )}>
            {value}
          </p>
          {trend === "up" && <ArrowUpRight className="h-3.5 w-3.5 shrink-0" style={{ color: COLORS.up }} />}
          {trend === "down" && <ArrowDownRight className="h-3.5 w-3.5 shrink-0" style={{ color: COLORS.down }} />}
        </div>
      </div>
    </div>
  )
}

export function ForeignFlowCharts({ data, isLoading }: ForeignFlowChartsProps) {
  // useMemo must be called unconditionally (before any returns)
  const volumePieData = useMemo(() => {
    if (!data) return []
    return [
      { name: "NĐTNN", value: data.foreign_volume, color: COLORS.orange },
      { name: "Trong nước", value: Math.max(0, data.total_volume - data.foreign_volume), color: COLORS.grey },
    ]
  }, [data])

  if (isLoading) return <ForeignFlowChartsSkeleton />

  if (!data) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted/30 flex items-center justify-center">
          <Globe className="w-8 h-8 text-muted-foreground/50" />
        </div>
        <p className="text-sm font-medium">Dữ liệu NĐTNN chưa khả dụng</p>
      </div>
    )
  }

  const foreignPct = data.foreign_pct_of_volume ?? 0
  const ownershipRatio = data.ownership_ratio ?? 0

  // Volume comparison
  const volumeVsAvg = data.avg_volume_2w && data.avg_volume_2w > 0
    ? ((data.total_volume / data.avg_volume_2w) * 100).toFixed(0)
    : null

  const isVolumeHigh = volumeVsAvg && Number(volumeVsAvg) > 100

  return (
    <div className="space-y-5">
      {/* Main Card: Radial Charts + Pie */}
      <Card className="border-border/50 bg-card/50">
        <CardContent className="p-5">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left: Radial Progress Charts */}
            <div>
              <h4 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <span className="w-1 h-4 rounded-full" style={{ backgroundColor: COLORS.orange }} />
                Tỷ lệ sở hữu & Giao dịch
              </h4>
              <div className="flex justify-around items-center py-2">
                <RadialProgress
                  value={ownershipRatio}
                  label="Sở hữu NĐTNN"
                />
                <RadialProgress
                  value={foreignPct / 100}
                  label="% KL Giao dịch"
                />
              </div>
            </div>

            {/* Right: Volume Distribution Pie */}
            <div>
              <h4 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <span className="w-1 h-4 rounded-full" style={{ backgroundColor: COLORS.orange }} />
                Phân bổ Khối lượng
              </h4>
              <div className="flex items-center gap-4">
                <div className="w-28 h-28 shrink-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={volumePieData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={32}
                        outerRadius={50}
                        paddingAngle={3}
                        strokeWidth={0}
                      >
                        {volumePieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex-1 space-y-3">
                  {volumePieData.map((item, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <span
                        className="w-3 h-3 rounded-sm shrink-0"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="text-sm text-muted-foreground flex-1">{item.name}</span>
                      <span className="text-sm font-semibold text-foreground tabular-nums">
                        {formatVolume(item.value)}
                      </span>
                    </div>
                  ))}
                  {/* Total */}
                  <div className="flex items-center gap-3 pt-2 border-t border-border/50">
                    <span className="w-3 h-3 shrink-0" />
                    <span className="text-sm text-muted-foreground flex-1">Tổng</span>
                    <span className="text-sm font-bold text-foreground tabular-nums">
                      {formatVolume(data.total_volume)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatItem
          icon={Globe}
          label="KL Nước Ngoài"
          value={formatVolume(data.foreign_volume)}
          highlight
        />
        <StatItem
          icon={Users}
          label="Tỷ lệ sở hữu"
          value={formatPct(data.ownership_ratio)}
        />
        <StatItem
          icon={Percent}
          label="% KL Giao dịch"
          value={data.foreign_pct_of_volume != null ? `${data.foreign_pct_of_volume.toFixed(1)}%` : "N/A"}
        />
        <StatItem
          icon={TrendingUp}
          label="So với TB 2 tuần"
          value={volumeVsAvg ? `${volumeVsAvg}%` : "N/A"}
          highlight={!!isVolumeHigh}
          trend={isVolumeHigh ? "up" : volumeVsAvg && Number(volumeVsAvg) < 100 ? "down" : null}
        />
      </div>

      {/* Additional Info Row */}
      <Card className="border-border/50 bg-card/50">
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="flex items-center justify-between p-3 rounded-lg bg-muted/20">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4" style={{ color: COLORS.orange }} />
                <span className="text-sm text-muted-foreground">Room còn lại</span>
              </div>
              <span className="text-sm font-semibold text-foreground tabular-nums">
                {formatVolume(data.foreign_room)}
              </span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg bg-muted/20">
              <span className="text-sm text-muted-foreground">Tổng KL phiên</span>
              <span className="text-sm font-semibold text-foreground tabular-nums">
                {formatVolume(data.total_volume)}
              </span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg bg-muted/20">
              <span className="text-sm text-muted-foreground">TB 2 tuần</span>
              <span className="text-sm font-semibold text-foreground tabular-nums">
                {data.avg_volume_2w ? formatVolume(data.avg_volume_2w) : "N/A"}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Timestamp */}
      <p className="text-xs text-center text-muted-foreground">
        Cập nhật: {new Date(data.last_updated).toLocaleDateString("vi-VN", {
          weekday: "long", day: "2-digit", month: "2-digit", year: "numeric"
        })} • {new Date(data.last_updated).toLocaleTimeString("vi-VN", {
          hour: "2-digit", minute: "2-digit"
        })}
      </p>
    </div>
  )
}

function ForeignFlowChartsSkeleton() {
  return (
    <div className="space-y-5">
      <Card className="border-border/50">
        <CardContent className="p-5">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <Skeleton className="h-5 w-40 mb-4" />
              <div className="flex justify-around">
                <Skeleton className="w-28 h-28 rounded-full" />
                <Skeleton className="w-28 h-28 rounded-full" />
              </div>
            </div>
            <div>
              <Skeleton className="h-5 w-36 mb-4" />
              <div className="flex items-center gap-4">
                <Skeleton className="w-28 h-28 rounded-full" />
                <div className="flex-1 space-y-3">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-[72px] rounded-lg" />
        ))}
      </div>
      <Card className="border-border/50">
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 rounded-lg" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
