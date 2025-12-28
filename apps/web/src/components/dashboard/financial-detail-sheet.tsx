"use client"

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { HealthScoreCard } from "./financial-health/health-score-card"
import { TrendChartsCard } from "./financial-trends/trend-charts-card"
import { PeerComparisonCard } from "./peer-comparison/peer-comparison-card"
import { FCFAnalysisCard } from "./fcf-analysis/fcf-analysis-card"
import type { FinancialStatementItem } from "@/lib/api"

interface FinancialDetailSheetProps {
  stock: FinancialStatementItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function FinancialDetailSheet({
  stock,
  open,
  onOpenChange,
}: FinancialDetailSheetProps) {
  const symbol = stock?.symbol || null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl md:max-w-2xl overflow-hidden p-0">
        <SheetHeader className="px-6 pt-6 pb-2">
          <SheetTitle className="flex items-center gap-2">
            {stock ? (
              <>
                <span className="text-[hsl(var(--accent-orange))]">{stock.symbol}</span>
                <span className="text-muted-foreground font-normal text-sm truncate">
                  - {stock.company_name}
                </span>
              </>
            ) : (
              "Chi tiết cổ phiếu"
            )}
          </SheetTitle>
        </SheetHeader>

        <div className="h-[calc(100vh-80px)] overflow-y-auto px-6 pb-8">
          <div className="space-y-4">
            <HealthScoreCard symbol={symbol} />
            <TrendChartsCard symbol={symbol} />
            <PeerComparisonCard symbol={symbol} />
            <FCFAnalysisCard symbol={symbol} />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
