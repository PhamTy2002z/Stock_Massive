"use client"

import { TrendingUp, Activity, Building2 } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { formatRatio } from "./shared"

// Summary Cards Component
export function SummaryCards({
  totalSpikes,
  avgRatio,
  topIndustry,
}: {
  totalSpikes: number
  avgRatio: number
  topIndustry: string
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Card className="bg-card/50 border-border/50">
        <CardContent className="p-4 flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <TrendingUp className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Tổng CP đột biến</p>
            <p className="text-2xl font-bold tabular-nums">{totalSpikes}</p>
          </div>
        </CardContent>
      </Card>
      <Card className="bg-card/50 border-border/50">
        <CardContent className="p-4 flex items-center gap-3">
          <div className="p-2 rounded-lg bg-foreground/10">
            <Activity className="h-5 w-5 text-foreground" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Tỷ lệ TB</p>
            <p className="text-2xl font-bold tabular-nums">{formatRatio(avgRatio)}</p>
          </div>
        </CardContent>
      </Card>
      <Card className="bg-card/50 border-border/50">
        <CardContent className="p-4 flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-500/10">
            <Building2 className="h-5 w-5 text-blue-500" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Ngành nổi bật</p>
            <p className="text-lg font-semibold truncate max-w-[180px]">{topIndustry || "-"}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
