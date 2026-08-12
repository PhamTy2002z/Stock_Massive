"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { Activity, RefreshCw, Clock } from "lucide-react"
import { useHealthScore } from "@/hooks/use-health-score"
import { HealthRadarChart } from "./health-radar-chart"
import { ScoreBreakdown } from "./score-breakdown"
import { FScoreIndicator } from "./f-score-indicator"
import { cn } from "@/lib/utils"
import { formatDistanceToNow } from "date-fns"

interface HealthScoreCardProps {
  symbol: string
  className?: string
}

export function HealthScoreCard({ symbol, className }: HealthScoreCardProps) {
  const { data, dataUpdatedAt, refetch, isRefetching } = useHealthScore(symbol)

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Activity className="h-5 w-5" />
          Financial Health Score
          <span className="ml-auto text-foreground font-bold">{data.symbol}</span>
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Time range: Q4 2024 | Industry avg: 65
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid md:grid-cols-2 gap-6">
          {/* Radar Chart */}
          <div>
            <HealthRadarChart dimensions={data.dimensions} />
          </div>

          {/* Score Details */}
          <div className="space-y-6">
            {/* Overall Score */}
            <div className="text-center p-4 bg-muted/30 rounded-lg">
              <div className="text-sm text-muted-foreground">Overall Score</div>
              <div className={cn(
                "text-4xl font-bold tabular-nums",
                data.health_score >= 70 ? "text-positive" :
                data.health_score >= 50 ? "text-yellow-500" : "text-red-500"
              )}>
                {data.health_score}
                <span className="text-lg text-muted-foreground">/100</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                vs Q3: +5 | Industry avg: 65
              </p>
            </div>

            {/* F-Score */}
            <FScoreIndicator score={data.f_score} details={data.f_score_details} />

            {/* Dimension Breakdown */}
            <div>
              <h4 className="text-sm font-medium mb-3">Score Breakdown</h4>
              <ScoreBreakdown dimensions={data.dimensions} />
            </div>
          </div>
        </div>

        {/* Last Updated */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-4 pt-4 border-t border-border/50">
          <Clock className="h-3 w-3" />
          <span>Last updated: {formatDistanceToNow(dataUpdatedAt)} ago</span>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 ml-auto"
            onClick={() => refetch()}
            disabled={isRefetching}
          >
            <RefreshCw className={cn("h-3 w-3", isRefetching && "animate-spin")} />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function HealthScoreCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
      </CardHeader>
      <CardContent>
        <div className="grid md:grid-cols-2 gap-6">
          <Skeleton className="h-[250px]" />
          <div className="space-y-4">
            <Skeleton className="h-20" />
            <Skeleton className="h-16" />
            <Skeleton className="h-32" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
