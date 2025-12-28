"use client"

import { useIntradayOrderStats } from "@/hooks/use-intraday-order-stats"
import { usePriceDepth } from "@/hooks/use-price-depth"
import { OrderFlowCharts } from "./widgets/order-flow-charts"
import { PriceDepthChart } from "./widgets/price-depth-chart"
import { RefreshCw, Clock, Activity, BarChart3 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface OrderFlowSubtabProps {
  symbol: string
}

function formatSessionDate(dateStr: string | undefined): string {
  if (!dateStr) return ""
  const date = new Date(dateStr)
  return date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" })
}

export default function OrderFlowSubtab({ symbol }: OrderFlowSubtabProps) {
  const orderStats = useIntradayOrderStats(symbol)
  const priceDepth = usePriceDepth(symbol)

  const handleRefresh = () => {
    orderStats.refetch()
    priceDepth.refetch()
  }

  const isLoading = orderStats.isLoading || priceDepth.isLoading
  const hasError = orderStats.error || priceDepth.error
  const sessionDate = formatSessionDate(orderStats.data?.date)

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

      {/* Content with tabs */}
      <Tabs defaultValue="order-stats" className="w-full">
        <TabsList className="grid w-full grid-cols-2 mb-4">
          <TabsTrigger value="order-stats" className="gap-2">
            <Activity className="h-4 w-4" />
            <span className="hidden sm:inline">Order Stats</span>
            <span className="sm:hidden">Stats</span>
          </TabsTrigger>
          <TabsTrigger value="price-depth" className="gap-2">
            <BarChart3 className="h-4 w-4" />
            <span className="hidden sm:inline">Price Depth</span>
            <span className="sm:hidden">Depth</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="order-stats" className="mt-0">
          <OrderFlowCharts data={orderStats.data} isLoading={orderStats.isLoading} />
        </TabsContent>

        <TabsContent value="price-depth" className="mt-0">
          <PriceDepthChart data={priceDepth.data} isLoading={priceDepth.isLoading} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
