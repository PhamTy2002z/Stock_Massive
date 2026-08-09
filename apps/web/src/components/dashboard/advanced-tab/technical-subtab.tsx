"use client"

import { useRatioSummary } from "@/hooks/use-ratio-summary"
import { RatioSummaryCard } from "./widgets/ratio-summary-card"
import { RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DataErrorNotice } from "./data-error-notice"

interface TechnicalSubtabProps {
  symbol: string
}

export default function TechnicalSubtab({ symbol }: TechnicalSubtabProps) {
  const ratios = useRatioSummary(symbol)

  const handleRefresh = () => {
    ratios.refetch()
  }

  const isLoading = ratios.isLoading

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

      {ratios.error && <DataErrorNotice error={ratios.error} />}

      <RatioSummaryCard data={ratios.data} isLoading={ratios.isLoading} />
    </div>
  )
}
