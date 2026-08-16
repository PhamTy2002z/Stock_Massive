"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { RatioSummaryResponse } from "@/lib/api"

interface RatioSummaryCardProps {
  data: RatioSummaryResponse | undefined
  isLoading: boolean
}

interface RatioItem {
  label: string
  value: number | null
  suffix?: string
  description?: string
  goodRange?: { min?: number; max?: number }
}

function formatRatio(value: number | null, suffix: string = ""): string {
  if (value === null || value === undefined) return "N/A"
  return `${value.toFixed(2)}${suffix}`
}

function getRatioColor(
  value: number | null,
  goodRange?: { min?: number; max?: number }
): string {
  if (value === null || !goodRange) return "text-foreground"
  const { min, max } = goodRange
  if (min !== undefined && value < min) return "text-negative"
  if (max !== undefined && value > max) return "text-negative"
  return "text-positive"
}

export function RatioSummaryCard({ data, isLoading }: RatioSummaryCardProps) {
  if (isLoading) {
    return <RatioSummaryCardSkeleton />
  }

  const ratios: RatioItem[] = [
    {
      label: "P/E",
      value: data?.pe ?? null,
      description: "Price to Earnings",
      goodRange: { max: 20 },
    },
    {
      label: "P/B",
      value: data?.pb ?? null,
      description: "Price to Book",
      goodRange: { max: 3 },
    },
    {
      label: "P/S",
      value: data?.ps ?? null,
      description: "Price to Sales",
    },
    {
      label: "ROE",
      value: data?.roe ?? null,
      suffix: "%",
      description: "Return on Equity",
      goodRange: { min: 15 },
    },
    {
      label: "ROA",
      value: data?.roa ?? null,
      suffix: "%",
      description: "Return on Assets",
      goodRange: { min: 5 },
    },
    {
      label: "ROIC",
      value: data?.roic ?? null,
      suffix: "%",
      description: "Return on Invested Capital",
      goodRange: { min: 10 },
    },
    {
      label: "Current Ratio",
      value: data?.current_ratio ?? null,
      description: "Khả năng thanh toán",
      goodRange: { min: 1.5, max: 3 },
    },
    {
      label: "D/E",
      value: data?.debt_to_equity ?? null,
      description: "Debt to Equity",
      goodRange: { max: 1.5 },
    },
  ]

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Chỉ Số Định Giá</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3">
          {ratios.map(({ label, value, suffix = "", description, goodRange }) => (
            <div
              key={label}
              className="flex items-center justify-between"
              title={description}
            >
              <span className="text-sm text-muted-foreground">{label}</span>
              <span
                className={cn(
                  "text-sm font-medium tabular-nums",
                  getRatioColor(value, goodRange)
                )}
              >
                {formatRatio(value, suffix)}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function RatioSummaryCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <Skeleton className="h-5 w-32" />
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between">
              <Skeleton className="h-4 w-12" />
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export { RatioSummaryCardSkeleton }
