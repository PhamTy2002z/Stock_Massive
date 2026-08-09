"use client"

import { useIntradayOrderStats } from "@/hooks/use-intraday-order-stats"
import { OrderFlowCharts } from "./widgets/order-flow-charts"
import { RefreshCw, Clock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { formatSessionDate } from "@/lib/format"
import { DataErrorNotice } from "./data-error-notice"

interface OrderFlowSubtabProps {
  symbol: string
}

export default function OrderFlowSubtab({ symbol }: OrderFlowSubtabProps) {
  const orderStats = useIntradayOrderStats(symbol)

  const handleRefresh = () => {
    orderStats.refetch()
  }

  const sessionDate = formatSessionDate(orderStats.data?.date ?? undefined)

  return (
    <div className="space-y-6">
      {/* Header with Refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium text-muted-foreground">
            Dữ liệu giao dịch trong phiên {sessionDate && `(${sessionDate})`}
          </h3>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={orderStats.isLoading}
          className="h-8"
        >
          <RefreshCw className={`h-4 w-4 mr-1 ${orderStats.isLoading ? "animate-spin" : ""}`} />
          Làm mới
        </Button>
      </div>

      {orderStats.error && <DataErrorNotice error={orderStats.error} />}

      <OrderFlowCharts data={orderStats.data} isLoading={orderStats.isLoading} />
    </div>
  )
}
