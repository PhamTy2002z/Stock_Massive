"use client"

import { useForeignSnapshot } from "@/hooks/use-foreign-snapshot"
import { ForeignFlowCharts } from "./widgets/foreign-flow-charts"
import { RefreshCw, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface MoneyFlowSubtabProps {
  symbol: string
}

function formatSessionDate(dateStr: string | undefined): string {
  if (!dateStr) return ""
  const date = new Date(dateStr)
  return date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" })
}

export default function MoneyFlowSubtab({ symbol }: MoneyFlowSubtabProps) {
  const foreign = useForeignSnapshot(symbol)

  const handleRefresh = () => {
    foreign.refetch()
  }

  const sessionDate = formatSessionDate(foreign.data?.last_updated)

  return (
    <div className="space-y-5">
      {/* Header with Refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-1 h-5 bg-white rounded-full" />
          <h3 className="text-sm font-semibold text-foreground">
            Dòng tiền NĐTNN
          </h3>
          {sessionDate && (
            <span className="text-xs text-muted-foreground bg-muted/50 px-2 py-0.5 rounded">
              {sessionDate}
            </span>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={foreign.isLoading}
          className={cn(
            "h-8 gap-1.5 text-muted-foreground hover:text-foreground",
            "hover:bg-muted/50 transition-colors"
          )}
        >
          <RefreshCw className={cn("h-3.5 w-3.5", foreign.isLoading && "animate-spin")} />
          <span className="text-xs">Làm mới</span>
        </Button>
      </div>

      {/* Error State */}
      {foreign.error && (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
          <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
          <p className="text-sm text-red-400">
            Có lỗi khi tải dữ liệu. Vui lòng thử lại.
          </p>
        </div>
      )}

      {/* Foreign Trading Charts */}
      <ForeignFlowCharts data={foreign.data} isLoading={foreign.isLoading} />

      {/* Info about limitations */}
      <div className="flex items-start gap-3 p-4 rounded-lg bg-muted/20 border border-border/30">
        <AlertCircle className="h-4 w-4 text-white shrink-0 mt-0.5" />
        <div className="text-sm">
          <p className="font-medium text-foreground mb-1.5">Giới hạn dữ liệu</p>
          <ul className="space-y-1 text-xs text-muted-foreground">
            <li className="flex items-start gap-2">
              <span className="w-1 h-1 rounded-full bg-muted-foreground mt-1.5 shrink-0" />
              Dữ liệu NĐTNN chỉ là snapshot hiện tại (không có lịch sử)
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1 h-1 rounded-full bg-muted-foreground mt-1.5 shrink-0" />
              Dữ liệu giao dịch tự doanh hiện không khả dụng qua API
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1 h-1 rounded-full bg-muted-foreground mt-1.5 shrink-0" />
              Dữ liệu được cập nhật định kỳ trong giờ giao dịch
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
