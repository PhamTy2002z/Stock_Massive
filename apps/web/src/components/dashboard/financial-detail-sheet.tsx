"use client"

import { Suspense } from "react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { HealthScoreCard, HealthScoreCardSkeleton } from "./financial-health/health-score-card"
import { TrendChartsCard, TrendChartsCardSkeleton } from "./financial-trends/trend-charts-card"
import { PeerComparisonCard, PeerComparisonCardSkeleton } from "./peer-comparison/peer-comparison-card"
import { FCFAnalysisCard, FCFAnalysisCardSkeleton } from "./fcf-analysis/fcf-analysis-card"
/**
 * The sheet only ever reads a ticker and a name off whatever row opened it, so
 * that is all it asks for. It used to take the row type of the profit ranking
 * table; tied to that, it would have gone out with it — and every card inside is
 * keyed on nothing but the symbol.
 */
interface FinancialDetailSubject {
  symbol: string
  company_name: string | null
}

interface FinancialDetailSheetProps {
  stock: FinancialDetailSubject | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function FinancialDetailSheet({
  stock,
  open,
  onOpenChange,
}: FinancialDetailSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl md:max-w-2xl overflow-hidden p-0">
        <SheetHeader className="px-6 pt-6 pb-2">
          <SheetTitle className="flex items-center gap-2">
            {stock ? (
              <>
                <span className="text-foreground font-semibold">{stock.symbol}</span>
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
          {stock ? (
            <div className="space-y-4">
              <Suspense fallback={<HealthScoreCardSkeleton />}>
                <HealthScoreCard symbol={stock.symbol} />
              </Suspense>
              <Suspense fallback={<TrendChartsCardSkeleton />}>
                <TrendChartsCard symbol={stock.symbol} />
              </Suspense>
              <Suspense fallback={<PeerComparisonCardSkeleton />}>
                <PeerComparisonCard symbol={stock.symbol} />
              </Suspense>
              <Suspense fallback={<FCFAnalysisCardSkeleton />}>
                <FCFAnalysisCard symbol={stock.symbol} />
              </Suspense>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Chọn một cổ phiếu để xem chi tiết
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
