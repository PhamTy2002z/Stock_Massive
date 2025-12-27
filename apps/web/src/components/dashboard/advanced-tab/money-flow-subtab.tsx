"use client"

import { useForeignTrading } from "@/hooks/use-foreign-trading"
import { usePropTrading } from "@/hooks/use-prop-trading"
import { ForeignFlowChart } from "./widgets/foreign-flow-chart"
import { PropFlowChart } from "./widgets/prop-flow-chart"
import { RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

interface MoneyFlowSubtabProps {
  symbol: string
}

export default function MoneyFlowSubtab({ symbol }: MoneyFlowSubtabProps) {
  const foreign = useForeignTrading(symbol)
  const prop = usePropTrading(symbol)

  const handleRefresh = () => {
    foreign.refetch()
    prop.refetch()
  }

  const isLoading = foreign.isLoading || prop.isLoading
  const hasError = foreign.error || prop.error

  return (
    <div className="space-y-6">
      {/* Header with Refresh */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">
          Dòng tiền 30 ngày gần nhất
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

      {/* Foreign Trading Chart */}
      <section className="rounded-lg border border-border/50 bg-card/50 p-4">
        <div className="flex items-center gap-2 mb-4">
          <h4 className="text-base font-semibold">Giao Dịch Nước Ngoài</h4>
          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-600 dark:text-blue-400">
            Foreign
          </span>
        </div>
        <ForeignFlowChart data={foreign.data} isLoading={foreign.isLoading} />
      </section>

      {/* Prop Trading Chart */}
      <section className="rounded-lg border border-border/50 bg-card/50 p-4">
        <div className="flex items-center gap-2 mb-4">
          <h4 className="text-base font-semibold">Giao Dịch Tự Doanh</h4>
          <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-600 dark:text-purple-400">
            Prop
          </span>
        </div>
        <PropFlowChart data={prop.data} isLoading={prop.isLoading} />
      </section>
    </div>
  )
}
