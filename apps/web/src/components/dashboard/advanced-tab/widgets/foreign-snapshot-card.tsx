"use client"

import { Skeleton } from "@/components/ui/skeleton"
import type { ForeignSnapshotResponse } from "@/lib/api"
import { Globe, TrendingUp, Users } from "lucide-react"

interface ForeignSnapshotCardProps {
  data: ForeignSnapshotResponse | undefined
  isLoading: boolean
}

function formatVolume(value: number): string {
  if (value >= 1000000000) return `${(value / 1000000000).toFixed(2)} tỷ`
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
  return value.toLocaleString("vi-VN")
}

function formatPct(value: number | null): string {
  if (value === null) return "N/A"
  return `${(value * 100).toFixed(2)}%`
}

export function ForeignSnapshotCard({ data, isLoading }: ForeignSnapshotCardProps) {
  if (isLoading) return <ForeignSnapshotCardSkeleton />

  if (!data) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <p className="text-sm">Dữ liệu NĐTNN chưa khả dụng</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Main Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 text-center">
          <Globe className="h-5 w-5 mx-auto mb-2 text-blue-600" />
          <p className="text-xs text-muted-foreground mb-1">KL Nước Ngoài</p>
          <p className="text-lg font-bold text-blue-600">{formatVolume(data.foreign_volume)}</p>
        </div>

        <div className="p-4 rounded-lg bg-purple-500/10 border border-purple-500/20 text-center">
          <Users className="h-5 w-5 mx-auto mb-2 text-purple-600" />
          <p className="text-xs text-muted-foreground mb-1">Tỷ lệ sở hữu</p>
          <p className="text-lg font-bold text-purple-600">{formatPct(data.ownership_ratio)}</p>
        </div>

        <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20 text-center">
          <TrendingUp className="h-5 w-5 mx-auto mb-2 text-green-600" />
          <p className="text-xs text-muted-foreground mb-1">% KL Giao dịch</p>
          <p className="text-lg font-bold text-green-600">
            {data.foreign_pct_of_volume?.toFixed(1) ?? "N/A"}%
          </p>
        </div>
      </div>

      {/* Additional Info */}
      <div className="p-3 rounded-lg bg-muted/30 border border-border/50 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Room còn lại</span>
          <span className="font-medium">{formatVolume(data.foreign_room)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Tổng KL phiên</span>
          <span className="font-medium">{formatVolume(data.total_volume)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Trung bình 2 tuần</span>
          <span className="font-medium">{data.avg_volume_2w ? formatVolume(data.avg_volume_2w) : "N/A"}</span>
        </div>
      </div>

      {/* Timestamp */}
      <p className="text-xs text-center text-muted-foreground">
        Phiên {new Date(data.last_updated).toLocaleDateString("vi-VN", { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" })}
        {" • "}{new Date(data.last_updated).toLocaleTimeString("vi-VN")}
      </p>
    </div>
  )
}

function ForeignSnapshotCardSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-24" />
    </div>
  )
}
