"use client"

import { useState } from "react"
import { useVolumeAnalysis } from "@/hooks/use-volume-analysis"
import { VolumeAnomalyChart, VolumeAnomalyChartSkeleton } from "./volume-anomaly-chart"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { AlertCircle, RefreshCw } from "lucide-react"

interface VolumeTabContentProps {
  symbol: string
}

export function VolumeTabContent({ symbol }: VolumeTabContentProps) {
  const [days, setDays] = useState(20)
  const { data, isLoading, error, refetch, isFetching } = useVolumeAnalysis(symbol, days)

  if (error) {
    return (
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            Không thể tải dữ liệu khối lượng
          </CardTitle>
          <CardDescription>
            {error instanceof Error ? error.message : "Đã xảy ra lỗi không mong muốn"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => refetch()} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Thử lại
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return <VolumeAnomalyChartSkeleton />
  }

  if (!data || data.time_slots.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Chưa có dữ liệu khối lượng</CardTitle>
          <CardDescription>
            Dữ liệu khối lượng trong ngày chưa được thu thập cho {symbol}.
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Baseline:</span>
          <Select value={days.toString()} onValueChange={(v) => setDays(parseInt(v))}>
            <SelectTrigger className="w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10 ngày</SelectItem>
              <SelectItem value="20">20 ngày</SelectItem>
              <SelectItem value="30">30 ngày</SelectItem>
              <SelectItem value="60">60 ngày</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button
          onClick={() => refetch()}
          variant="outline"
          size="sm"
          disabled={isFetching}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? "animate-spin" : ""}`} />
          Làm mới
        </Button>
      </div>

      {/* Chart */}
      <VolumeAnomalyChart
        data={data.time_slots}
        symbol={data.symbol}
        daysAnalyzed={data.days_analyzed}
        latestDate={data.latest_date}
      />

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Về phát hiện bất thường khối lượng</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>
            Biểu đồ so sánh khối lượng mỗi 5 phút với trung bình {days} ngày để phát hiện hoạt động giao dịch bất thường.
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li><strong>Tăng cao (1.5x-2x):</strong> Cao hơn trung bình vừa phải</li>
            <li><strong>Cao (2x-3x):</strong> Cao hơn trung bình đáng kể</li>
            <li><strong>Rất cao (&gt;3x):</strong> Đột biến khối lượng bất thường</li>
          </ul>
          <p className="text-xs mt-3">
            Nguồn dữ liệu: Dữ liệu intraday thu thập hàng ngày. Cập nhật: {data.latest_date || "N/A"}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
