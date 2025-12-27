"use client"

import { useOrderStats } from "@/hooks/use-order-stats"
import { usePriceDepth } from "@/hooks/use-price-depth"
import { OrderStatsTable } from "./widgets/order-stats-table"
import { PriceDepthWidget } from "./widgets/price-depth-widget"
import { RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

interface OrderFlowSubtabProps {
  symbol: string
}

export default function OrderFlowSubtab({ symbol }: OrderFlowSubtabProps) {
  const orderStats = useOrderStats(symbol)
  const priceDepth = usePriceDepth(symbol)

  const handleRefresh = () => {
    orderStats.refetch()
    priceDepth.refetch()
  }

  const isLoading = orderStats.isLoading || priceDepth.isLoading
  const hasError = orderStats.error || priceDepth.error

  return (
    <div className="space-y-6">
      {/* Header with Refresh */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">
          Dữ liệu 30 ngày gần nhất
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

      {/* Price Depth - Real-time */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <h4 className="text-base font-semibold">Price Depth</h4>
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-600 dark:text-green-400">
            Real-time
          </span>
        </div>
        <PriceDepthWidget data={priceDepth.data} isLoading={priceDepth.isLoading} />
      </section>

      {/* Order Stats - Historical */}
      <section>
        <h4 className="text-base font-semibold mb-4">Order Stats (30D)</h4>
        <OrderStatsTable data={orderStats.data} isLoading={orderStats.isLoading} />
      </section>
    </div>
  )
}
