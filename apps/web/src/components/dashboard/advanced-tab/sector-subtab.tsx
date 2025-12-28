"use client"

import { useSectorPeers } from "@/hooks/use-sector-peers"
import { SectorOverviewCard } from "./widgets/sector-overview-card"
import { PeerComparisonTable } from "./widgets/peer-comparison-table"
import { RefreshCw, AlertCircle, Building2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface SectorSubtabProps {
  symbol: string
}

function SectorSubtabSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-8 w-24" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}

export default function SectorSubtab({ symbol }: SectorSubtabProps) {
  const { data, isLoading, error, refetch, dataUpdatedAt } = useSectorPeers(symbol)

  if (isLoading) return <SectorSubtabSkeleton />

  if (error) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/20">
        <AlertCircle className="h-4 w-4 text-destructive shrink-0" />
        <p className="text-sm text-destructive">
          Có lỗi khi tải dữ liệu. Vui lòng thử lại.
        </p>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          Thử lại
        </Button>
      </div>
    )
  }

  if (!data || data.peers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
        <p className="text-muted-foreground">Không tìm thấy công ty cùng ngành</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Thử chọn mã cổ phiếu khác để so sánh
        </p>
      </div>
    )
  }

  // Format last updated time per design-guidelines.md
  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : null

  return (
    <div className="space-y-6">
      {/* Header with refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-1 h-5 bg-primary rounded-full" />
          <h3 className="text-sm font-semibold text-foreground">
            So sánh ngành
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-xs text-muted-foreground">
              Cập nhật: {lastUpdated}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
            className={cn(
              "h-8 gap-1.5 text-muted-foreground hover:text-foreground",
              "hover:bg-muted/50 transition-colors"
            )}
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
            <span className="text-xs">Làm mới</span>
          </Button>
        </div>
      </div>

      {/* Sector Overview */}
      <SectorOverviewCard
        icbCode={data.icb_code}
        icbName={data.icb_name}
        peerCount={data.peers.length}
        median={data.sector_median}
        targetPremium={data.target_premium}
      />

      {/* Peer Table */}
      <PeerComparisonTable
        peers={data.peers}
        targetSymbol={symbol}
      />

      {/* Legend - Using semantic colors per design-guidelines.md */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-[hsl(var(--stock-up))]/20 border border-[hsl(var(--stock-up))]" />
          Premium (trên +5%)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-muted border border-border" />
          Trung bình (±5%)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-[hsl(var(--stock-down))]/20 border border-[hsl(var(--stock-down))]" />
          Discount (dưới -5%)
        </span>
      </div>
    </div>
  )
}
