"use client"

import { Card, CardContent } from "@/components/ui/card"
import type { SectorMedian } from "@/lib/api"
import { Building2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface SectorOverviewCardProps {
  icbCode: string
  icbName: string
  peerCount: number
  median: SectorMedian
  targetPremium?: Record<string, number | null>
}

interface MetricItemProps {
  label: string
  value: number | null
  unit: string
  premium?: number | null
}

function MetricItem({ label, value, unit, premium }: MetricItemProps) {
  const formattedValue = value !== null ? value.toFixed(2) : "-"

  // 5-tier color system matching PremiumBadge
  const getPremiumColor = (p: number) => {
    if (p > 30) return "text-positive"
    if (p > 10) return "text-[hsl(var(--stock-up))]"
    if (p >= -10) return "text-muted-foreground"
    if (p >= -30) return "text-[hsl(var(--stock-down))]"
    return "text-negative"
  }

  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold tabular-nums">
        {formattedValue}{unit}
      </p>
      {premium !== null && premium !== undefined && (
        <p className={cn("text-xs tabular-nums", getPremiumColor(premium))}>
          {premium > 0 ? "+" : ""}{premium.toFixed(1)}% vs median
        </p>
      )}
    </div>
  )
}

export function SectorOverviewCard({
  icbCode,
  icbName,
  peerCount,
  median,
  targetPremium,
}: SectorOverviewCardProps) {
  return (
    <Card className="bg-surface-sunken border-border">
      <CardContent className="p-4">
        {/* Header with ICB info */}
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg bg-primary/10">
            <Building2 className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h4 className="font-semibold text-foreground">{icbName}</h4>
            <p className="text-xs text-muted-foreground">
              ICB: {icbCode} • {peerCount} công ty
            </p>
          </div>
        </div>

        {/* Sector Median KPIs - 4-column grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <MetricItem
            label="P/E Median"
            value={median.pe}
            unit="x"
            premium={targetPremium?.pe}
          />
          <MetricItem
            label="P/B Median"
            value={median.pb}
            unit="x"
            premium={targetPremium?.pb}
          />
          <MetricItem
            label="ROE Median"
            value={median.roe}
            unit="%"
            premium={targetPremium?.roe}
          />
          <MetricItem
            label="ROA Median"
            value={median.roa}
            unit="%"
            premium={targetPremium?.roa}
          />
        </div>

        {/* Time range context */}
        <p className="mt-3 text-xs text-muted-foreground text-right">
          Dữ liệu: TTM (12 tháng gần nhất)
        </p>
      </CardContent>
    </Card>
  )
}
