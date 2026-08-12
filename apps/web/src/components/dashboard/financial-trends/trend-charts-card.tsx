"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"
import { TrendingUp, BarChart3, LineChart, Wallet } from "lucide-react"
import { useTrendMetrics } from "@/hooks/use-trend-metrics"
import { RevenueProfitChart } from "./revenue-profit-chart"
import { MarginTrendChart } from "./margin-trend-chart"
import { RoeRoaChart } from "./roe-roa-chart"
import { CashFlowChart } from "./cash-flow-chart"

interface TrendChartsCardProps {
  symbol: string
  className?: string
}

export function TrendChartsCard({ symbol, className }: TrendChartsCardProps) {
  const { data } = useTrendMetrics(symbol)

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <TrendingUp className="h-5 w-5" />
          Phân tích xu hướng
          <span className="ml-auto text-foreground font-bold">{data.symbol}</span>
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {data.periods.length} quý gần nhất
        </p>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="revenue" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="revenue" className="text-xs">
              <BarChart3 className="h-4 w-4 mr-1" />
              Doanh thu
            </TabsTrigger>
            <TabsTrigger value="margin" className="text-xs">
              <LineChart className="h-4 w-4 mr-1" />
              Biên LN
            </TabsTrigger>
            <TabsTrigger value="roe" className="text-xs">
              <TrendingUp className="h-4 w-4 mr-1" />
              ROE/ROA
            </TabsTrigger>
            <TabsTrigger value="cashflow" className="text-xs">
              <Wallet className="h-4 w-4 mr-1" />
              Dòng tiền
            </TabsTrigger>
          </TabsList>

          <TabsContent value="revenue" className="mt-4">
            <RevenueProfitChart data={data} />
          </TabsContent>

          <TabsContent value="margin" className="mt-4">
            <MarginTrendChart data={data} />
          </TabsContent>

          <TabsContent value="roe" className="mt-4">
            <RoeRoaChart data={data} />
          </TabsContent>

          <TabsContent value="cashflow" className="mt-4">
            <CashFlowChart data={data} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

export function TrendChartsCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-24 mt-1" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-10 w-full mb-4" />
        <Skeleton className="h-[300px] w-full" />
      </CardContent>
    </Card>
  )
}
