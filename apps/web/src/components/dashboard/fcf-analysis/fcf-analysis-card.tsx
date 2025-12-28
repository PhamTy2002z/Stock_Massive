"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Wallet } from "lucide-react"
import { useFCFAnalysis } from "@/hooks/use-fcf-analysis"
import { FCFWaterfall } from "./fcf-waterfall"
import { CCCIndicator } from "./ccc-indicator"

interface FCFAnalysisCardProps {
  symbol: string | null
  className?: string
}

export function FCFAnalysisCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-[280px]" />
      </CardContent>
    </Card>
  )
}

export function FCFAnalysisCard({ symbol, className }: FCFAnalysisCardProps) {
  const { data, isLoading, error } = useFCFAnalysis(symbol)

  if (!symbol) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-[350px] text-muted-foreground">
          Chọn một cổ phiếu để xem FCF Analysis
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return <FCFAnalysisCardSkeleton className={className} />
  }

  if (error || !data) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-[350px] text-destructive">
          Không thể tải FCF Analysis
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Wallet className="h-5 w-5" />
          FCF Analysis
          <span className="text-sm font-normal text-muted-foreground">- {data.period}</span>
          <span className="ml-auto text-primary font-bold">{data.symbol}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <FCFWaterfall data={data} />

        {/* Metrics Row */}
        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border/50">
          <div className="text-center">
            <div className="text-sm text-muted-foreground">FCF Margin</div>
            <div className="text-xl font-bold text-[hsl(var(--accent-orange))]">
              {data.fcf_margin ? `${(data.fcf_margin * 100).toFixed(1)}%` : "-"}
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-muted-foreground">FCF Yield</div>
            <div className="text-xl font-bold text-[hsl(var(--accent-orange))]">
              {data.fcf_yield ? `${(data.fcf_yield * 100).toFixed(2)}%` : "-"}
            </div>
          </div>
        </div>

        {/* CCC */}
        <CCCIndicator
          ccc={data.ccc}
          dso={data.dso}
          dio={data.dio}
          dpo={data.dpo}
        />
      </CardContent>
    </Card>
  )
}
