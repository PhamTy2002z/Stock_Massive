"use client"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { MarketContextSector } from "@/lib/api"

interface SectorContextCardProps {
  sector: MarketContextSector | null
}

function getRankVariant(
  rank: number,
  total: number
): "default" | "secondary" | "outline" {
  const percentile = rank / total
  if (percentile <= 0.2) return "default"
  if (percentile <= 0.5) return "secondary"
  return "outline"
}

export function SectorContextCard({ sector }: SectorContextCardProps) {
  if (!sector) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Ngữ Cảnh Ngành</CardTitle>
          <CardDescription>Không phân loại ngành</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Cổ phiếu này không thuộc ngành nào trong hệ thống phân loại.
          </p>
        </CardContent>
      </Card>
    )
  }

  const percentile = sector.rank / sector.total
  const rankLabel =
    percentile <= 0.2
      ? "Top 20% ngành"
      : percentile <= 0.5
        ? "Trên trung bình"
        : "Dưới trung bình"

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Ngữ Cảnh Ngành</CardTitle>
        <CardDescription>{sector.icb_name}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Sector Rank */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              Xếp hạng ngành
            </span>
            <Badge variant={getRankVariant(sector.rank, sector.total)}>
              #{sector.rank} / {sector.total}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">{rankLabel}</p>
        </div>

        {/* Top Peers */}
        {sector.top_peers && sector.top_peers.length > 0 && (
          <div className="space-y-2">
            <span className="text-sm font-medium">Top cổ phiếu cùng ngành</span>
            <div className="space-y-1">
              {sector.top_peers.map((peer) => (
                <div
                  key={peer.symbol}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-muted-foreground font-mono">
                    {peer.symbol}
                  </span>
                  <span
                    className={
                      peer.change_pct >= 0 ? "text-green-500" : "text-red-500"
                    }
                  >
                    {peer.change_pct >= 0 ? "+" : ""}
                    {peer.change_pct.toFixed(2)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// Skeleton
export function SectorContextCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="h-5 w-32 bg-muted animate-pulse rounded" />
        <div className="h-4 w-24 bg-muted animate-pulse rounded mt-1" />
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <div className="h-4 w-24 bg-muted animate-pulse rounded" />
            <div className="h-5 w-16 bg-muted animate-pulse rounded" />
          </div>
          <div className="h-3 w-28 bg-muted animate-pulse rounded" />
        </div>
        <div className="space-y-2">
          <div className="h-4 w-36 bg-muted animate-pulse rounded" />
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 w-12 bg-muted animate-pulse rounded" />
              <div className="h-4 w-14 bg-muted animate-pulse rounded" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
