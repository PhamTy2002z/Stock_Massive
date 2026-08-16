"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import { RefreshCw } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { useVolumeSpikes } from "@/hooks/use-volume-spikes"
import type { SignalScope } from "@/lib/api"
import { CoverageBand } from "./coverage-band"
import { InsufficientDataNotice } from "./insufficient-notice"
import { ScopeTabs } from "./scope-tabs"
import { SpikeStockTable } from "./spike-stock-table"
import { UnevaluablePanel } from "./unevaluable-panel"
import { useSortedPagedRows } from "./use-sorted-paged-rows"

interface VolumeSpikeDashboardProps {
  className?: string
}

/**
 * Volume spikes for one Signal Scope.
 *
 * The two scopes are "Nhóm dẫn đầu lợi nhuận" and "Toàn bộ Universe" — never
 * "toàn thị trường". This system follows a bounded set of symbols, and a screen
 * that calls it the market makes a claim the data cannot support. The bound
 * itself is not shown: it is a limit on collection, not a quota anyone bought.
 */
export function VolumeSpikeDashboard({ className }: VolumeSpikeDashboardProps) {
  const [scope, setScope] = useState<SignalScope>("profit_leaders")
  const [threshold, setThreshold] = useState(1.5)
  const [exchange, setExchange] = useState<string>()

  const { data, isFetching, refetch } = useVolumeSpikes({
    scope,
    threshold,
    // The ranking spans HOSE and HNX together, so the board filter belongs to
    // the Universe screen alone — the API refuses it on the other.
    exchange: scope === "universe" ? exchange : undefined,
  })

  const table = useSortedPagedRows(data.spikes)
  const insufficient = data.coverage.state === "insufficient_data"

  return (
    <div className={cn("space-y-6", className)}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Khối lượng đột biến</h1>
          <p className="text-sm text-muted-foreground">
            Khối lượng một phiên so với trung bình 20 phiên giao dịch liền trước
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="p-2 rounded-md hover:bg-muted transition-colors disabled:opacity-50 self-end"
          title="Làm mới"
          aria-label="Làm mới"
        >
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
        </button>
      </div>

      <ScopeTabs scope={scope} onScopeChange={setScope} />

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <Label className="text-sm text-muted-foreground whitespace-nowrap">
            Ngưỡng:
          </Label>
          <Select
            value={String(threshold)}
            onValueChange={(value) => setThreshold(Number(value))}
          >
            <SelectTrigger className="w-[100px] h-9 bg-background">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1.5">≥1.5x</SelectItem>
              <SelectItem value="2">≥2x</SelectItem>
              <SelectItem value="2.5">≥2.5x</SelectItem>
              <SelectItem value="3">≥3x</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {scope === "universe" && (
          <div className="flex items-center gap-2">
            <Label className="text-sm text-muted-foreground whitespace-nowrap">
              Sàn:
            </Label>
            <Select
              value={exchange || "all"}
              onValueChange={(value) =>
                setExchange(value === "all" ? undefined : value)
              }
            >
              <SelectTrigger className="w-[100px] h-9 bg-background">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tất cả</SelectItem>
                <SelectItem value="HOSE">HOSE</SelectItem>
                <SelectItem value="HNX">HNX</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      <CoverageBand signal={data} />

      {insufficient ? (
        <InsufficientDataNotice />
      ) : data.spikes.length > 0 ? (
        <SpikeStockTable table={table} />
      ) : (
        <div className="rounded-lg border border-border bg-card p-8 text-center">
          <p className="text-muted-foreground">
            Không có mã nào đạt ngưỡng {threshold}x trong phiên này.
          </p>
        </div>
      )}

      <UnevaluablePanel symbols={data.unevaluable} />
    </div>
  )
}
