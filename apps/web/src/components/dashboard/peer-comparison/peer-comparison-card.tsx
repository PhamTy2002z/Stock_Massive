"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Users } from "lucide-react"
import { useSectorPeers } from "@/hooks/use-sector-peers"
import { PeerMetricsTable } from "./peer-metrics-table"

interface PeerComparisonCardProps {
  symbol: string
  className?: string
}

export function PeerComparisonCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-[180px]" />
      </CardContent>
    </Card>
  )
}

export function PeerComparisonCard({ symbol, className }: PeerComparisonCardProps) {
  const { data } = useSectorPeers(symbol)

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Users className="h-5 w-5" />
          Peer Comparison
          <span className="text-sm font-normal text-muted-foreground">
            - {data.icb_name} (ICB: {data.icb_code})
          </span>
          <span className="ml-auto font-bold text-foreground">{data.symbol}</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <PeerMetricsTable peers={data.peers} targetSymbol={data.symbol} />
      </CardContent>
    </Card>
  )
}
