"use client"

import { useRatioSummary } from "@/hooks/use-ratio-summary"
import { useTradingStats } from "@/hooks/use-trading-stats"
import { RatioSummaryCard } from "./widgets/ratio-summary-card"
import { TradingStatsCard } from "./widgets/trading-stats-card"
import { RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

interface TechnicalSubtabProps {
  symbol: string
}

export default function TechnicalSubtab({ symbol }: TechnicalSubtabProps) {
  const ratios = useRatioSummary(symbol)
  const stats = useTradingStats(symbol)

  const handleRefresh = () => {
    ratios.refetch()
    stats.refetch()
  }

  const isLoading = ratios.isLoading || stats.isLoading
  const hasError = ratios.error || stats.error

  return (
    <div className="space-y-6">
      {/* Header with Refresh */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">
          Phân tích kỹ thuật & chỉ số tài chính
        </h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={isLoading}
          className="h-8"
        >
          <RefreshCw className={`h-4 w-4 mr-1 ${isLoading ? "animate-spin" : ""}`} />
          Làm mới
        </Button>
      </div>

      {hasError && (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive text-sm">
          Có lỗi khi tải dữ liệu. Vui lòng thử lại.
        </div>
      )}

      {/* Cards Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        <RatioSummaryCard data={ratios.data} isLoading={ratios.isLoading} />
        <TradingStatsCard data={stats.data} isLoading={stats.isLoading} />
      </div>
    </div>
  )
}
