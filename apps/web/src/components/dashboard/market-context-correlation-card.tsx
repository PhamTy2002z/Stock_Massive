"use client"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, TrendingDown } from "lucide-react"
import type { MarketContextMetrics } from "@/lib/api"

interface CorrelationCardProps {
  metrics: MarketContextMetrics
}

function formatMetric(value: number | null, decimals = 2): string {
  if (value === null) return "N/A"
  return value.toFixed(decimals)
}

function getBetaVariant(
  beta: number | null
): "default" | "secondary" | "destructive" {
  if (beta === null) return "secondary"
  if (beta > 1.2) return "destructive"
  if (beta < 0.8) return "default"
  return "secondary"
}

function getCorrelationVariant(
  corr: number | null
): "default" | "secondary" {
  if (corr === null) return "secondary"
  if (Math.abs(corr) > 0.7) return "default"
  return "secondary"
}

export function CorrelationCard({ metrics }: CorrelationCardProps) {
  const rsOutperform = metrics.rs_market_20d !== null && metrics.rs_market_20d > 1

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Tương Quan Thị Trường</CardTitle>
        <CardDescription>So với VNINDEX</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Beta */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Beta (20D)</span>
            <Badge variant={getBetaVariant(metrics.beta_20d)}>
              {formatMetric(metrics.beta_20d)}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            {metrics.beta_20d !== null
              ? metrics.beta_20d > 1
                ? "Biến động cao hơn thị trường"
                : "Biến động thấp hơn thị trường"
              : "Không đủ dữ liệu"}
          </p>
        </div>

        {/* Correlation */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              Tương quan (20D)
            </span>
            <Badge variant={getCorrelationVariant(metrics.correlation_20d)}>
              {formatMetric(metrics.correlation_20d)}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            {metrics.correlation_20d !== null
              ? Math.abs(metrics.correlation_20d) > 0.7
                ? "Tương quan mạnh"
                : "Tương quan yếu"
              : "Không đủ dữ liệu"}
          </p>
        </div>

        {/* Relative Strength */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              Sức mạnh tương đối (20D)
            </span>
            <div className="flex items-center gap-2">
              {rsOutperform ? (
                <TrendingUp className="h-4 w-4 text-green-500" />
              ) : (
                <TrendingDown className="h-4 w-4 text-red-500" />
              )}
              <Badge variant={rsOutperform ? "default" : "secondary"}>
                {formatMetric(metrics.rs_market_20d)}
              </Badge>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            {metrics.rs_market_20d !== null
              ? rsOutperform
                ? "Vượt trội so với thị trường"
                : "Yếu hơn thị trường"
              : "Không đủ dữ liệu"}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

// Skeleton
export function CorrelationCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="h-5 w-36 bg-muted animate-pulse rounded" />
        <div className="h-4 w-24 bg-muted animate-pulse rounded mt-1" />
      </CardHeader>
      <CardContent className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-1">
            <div className="flex items-center justify-between">
              <div className="h-4 w-24 bg-muted animate-pulse rounded" />
              <div className="h-5 w-12 bg-muted animate-pulse rounded" />
            </div>
            <div className="h-3 w-40 bg-muted animate-pulse rounded" />
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
