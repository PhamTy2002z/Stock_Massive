"use client"

import { cn } from "@/lib/utils"
import type { FCFAnalysisResponse } from "@/lib/api"

interface FCFWaterfallProps {
  data: FCFAnalysisResponse
}

function formatBillions(value: number | null): string {
  if (value === null) return "-"
  const abs = Math.abs(value)
  const sign = value < 0 ? "-" : ""
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(1)}T`
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(1)}B`
  return `${sign}${(abs / 1e6).toFixed(0)}M`
}

export function FCFWaterfall({ data }: FCFWaterfallProps) {
  const maxValue = Math.max(
    Math.abs(data.net_income || 0),
    Math.abs(data.cfo || 0),
    Math.abs(data.fcf || 0)
  )

  const getWidth = (value: number | null) => {
    if (!value || !maxValue) return 0
    return (Math.abs(value) / maxValue) * 100
  }

  const items = [
    { label: "Net Income", value: data.net_income, color: "bg-muted-foreground" },
    // bg-foreground, not bg-white: these two bars are the emphasised pair, and
    // white was only ever correct while the app rendered on a dark tile.
    { label: "CFO", value: data.cfo, color: "bg-foreground" },
    { label: "CapEx", value: data.capex, color: "bg-red-500" },
    { label: "FCF", value: data.fcf, color: "bg-foreground" },
  ]

  return (
    <div className="space-y-4">
      {items.map((item) => (
        <div key={item.label} className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">{item.label}</span>
            <span className={cn(
              "font-medium tabular-nums",
              (item.value || 0) >= 0 ? "text-green-500" : "text-red-500"
            )}>
              {formatBillions(item.value)}
            </span>
          </div>
          <div className="h-6 bg-muted rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all", item.color)}
              style={{ width: `${getWidth(item.value)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
