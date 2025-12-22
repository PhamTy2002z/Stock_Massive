"use client"

import { useState, useMemo } from "react"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  RefreshCw,
  ChevronDown,
  TrendingUp,
  Activity,
  Building2,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { useVolumeSpikes } from "@/hooks/use-volume-spikes"
import { VolumeSpikeChart } from "./volume-spike-chart"
import type {
  IndustryVolumeSpikeGroup,
  VolumeSpikeAnomalyLevel,
} from "@/lib/api"

interface VolumeSpikeDashboardProps {
  className?: string
}

// Anomaly level colors
const ANOMALY_COLORS: Record<VolumeSpikeAnomalyLevel, string> = {
  normal: "hsl(var(--muted-foreground))",
  elevated: "hsl(45 93% 47%)",
  high: "hsl(25 95% 53%)",
  very_high: "hsl(0 84% 60%)",
}

const ANOMALY_BADGE_VARIANTS: Record<VolumeSpikeAnomalyLevel, "default" | "secondary" | "destructive" | "outline"> = {
  normal: "secondary",
  elevated: "outline",
  high: "default",
  very_high: "destructive",
}

// Format helpers
function formatVolume(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`
  return value.toLocaleString("vi-VN")
}

function formatPercent(value: number | null): string {
  if (value === null) return "-"
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

function formatRatio(value: number): string {
  return `${value.toFixed(1)}x`
}

// Summary Cards Component
function SummaryCards({
  totalSpikes,
  avgRatio,
  topIndustry,
}: {
  totalSpikes: number
  avgRatio: number
  topIndustry: string
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Card className="bg-card/50 border-border/50">
        <CardContent className="p-4 flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <TrendingUp className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Tổng CP đột biến</p>
            <p className="text-2xl font-bold tabular-nums">{totalSpikes}</p>
          </div>
        </CardContent>
      </Card>
      <Card className="bg-card/50 border-border/50">
        <CardContent className="p-4 flex items-center gap-3">
          <div className="p-2 rounded-lg bg-orange-500/10">
            <Activity className="h-5 w-5 text-orange-500" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Tỷ lệ TB</p>
            <p className="text-2xl font-bold tabular-nums">{formatRatio(avgRatio)}</p>
          </div>
        </CardContent>
      </Card>
      <Card className="bg-card/50 border-border/50">
        <CardContent className="p-4 flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-500/10">
            <Building2 className="h-5 w-5 text-blue-500" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Ngành nổi bật</p>
            <p className="text-lg font-semibold truncate max-w-[180px]">{topIndustry || "-"}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

// Industry Spike Group Component
function IndustrySpikeGroup({
  group,
  defaultOpen = false,
}: {
  group: IndustryVolumeSpikeGroup
  defaultOpen?: boolean
}) {
  const router = useRouter()
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const [sortField, setSortField] = useState<"spike_ratio" | "current_volume" | "price_change_pct">("spike_ratio")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc")
  const [page, setPage] = useState(1)
  const pageSize = 10

  const sortedStocks = useMemo(() => {
    return [...group.stocks].sort((a, b) => {
      const aVal = a[sortField] ?? -Infinity
      const bVal = b[sortField] ?? -Infinity
      return sortDir === "desc" ? (bVal > aVal ? 1 : -1) : (aVal > bVal ? 1 : -1)
    })
  }, [group.stocks, sortField, sortDir])

  const paginatedStocks = sortedStocks.slice((page - 1) * pageSize, page * pageSize)
  const totalPages = Math.ceil(sortedStocks.length / pageSize)

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortDir(sortDir === "desc" ? "asc" : "desc")
    } else {
      setSortField(field)
      setSortDir("desc")
    }
    setPage(1)
  }

  const SortIcon = ({ field }: { field: typeof sortField }) => {
    if (sortField !== field) return <ArrowUpDown className="h-3 w-3 opacity-50" />
    return sortDir === "desc" ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />
  }

  const handleRowClick = (symbol: string) => {
    router.push(`/analytics/deep-dive?symbol=${encodeURIComponent(symbol)}`)
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger className="w-full">
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
          <div className="flex items-center gap-3">
            <ChevronDown className={cn("h-4 w-4 transition-transform", isOpen && "rotate-180")} />
            <span className="font-medium">{group.icb_name}</span>
            <Badge variant="secondary" className="text-xs">
              {group.spike_count} CP
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>TB: {formatRatio(group.avg_spike_ratio)}</span>
          </div>
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-2 rounded-lg border border-border/50 bg-card/50 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] border-collapse">
              <thead>
                <tr className="border-b border-border/50 bg-muted/30">
                  <th className="py-2 px-3 text-left text-xs font-medium text-muted-foreground">Mã</th>
                  <th className="py-2 px-3 text-left text-xs font-medium text-muted-foreground">Công ty</th>
                  <th className="py-2 px-3 text-right text-xs font-medium text-muted-foreground">
                    <button onClick={() => toggleSort("current_volume")} className="inline-flex items-center gap-1 hover:text-foreground">
                      KL <SortIcon field="current_volume" />
                    </button>
                  </th>
                  <th className="py-2 px-3 text-right text-xs font-medium text-muted-foreground">
                    <button onClick={() => toggleSort("spike_ratio")} className="inline-flex items-center gap-1 hover:text-foreground">
                      Tỷ lệ <SortIcon field="spike_ratio" />
                    </button>
                  </th>
                  <th className="py-2 px-3 text-right text-xs font-medium text-muted-foreground">
                    <button onClick={() => toggleSort("price_change_pct")} className="inline-flex items-center gap-1 hover:text-foreground">
                      Giá <SortIcon field="price_change_pct" />
                    </button>
                  </th>
                  <th className="py-2 px-3 text-center text-xs font-medium text-muted-foreground">Mức độ</th>
                </tr>
              </thead>
              <tbody>
                {paginatedStocks.map((stock) => (
                  <tr
                    key={stock.symbol}
                    onClick={() => handleRowClick(stock.symbol)}
                    onKeyDown={(e) => e.key === "Enter" && handleRowClick(stock.symbol)}
                    tabIndex={0}
                    role="button"
                    aria-label={`Xem chi tiết ${stock.symbol}`}
                    className="border-b border-border/30 hover:bg-muted/20 transition-colors cursor-pointer focus:outline-none focus:bg-muted/30"
                  >
                    <td className="py-2 px-3">
                      <span className="text-sm font-semibold text-primary">{stock.symbol}</span>
                      <span className="ml-1.5 text-xs text-muted-foreground">{stock.exchange}</span>
                    </td>
                    <td className="py-2 px-3 text-sm text-foreground/90 max-w-[200px] truncate">
                      {stock.company_name || "-"}
                    </td>
                    <td className="py-2 px-3 text-sm text-right tabular-nums">
                      {formatVolume(stock.current_volume)}
                    </td>
                    <td className="py-2 px-3 text-sm text-right tabular-nums font-medium">
                      <span style={{ color: ANOMALY_COLORS[stock.anomaly_level] }}>
                        {formatRatio(stock.spike_ratio)}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-sm text-right tabular-nums">
                      <span className={stock.price_change_pct && stock.price_change_pct >= 0 ? "text-green-500" : "text-red-500"}>
                        {formatPercent(stock.price_change_pct)}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-center">
                      <Badge variant={ANOMALY_BADGE_VARIANTS[stock.anomaly_level]} className="text-xs">
                        {stock.anomaly_level === "very_high" ? ">3x" : stock.anomaly_level === "high" ? "2-3x" : "1.5-2x"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-3 py-2 border-t border-border/50 bg-muted/20">
              <span className="text-xs text-muted-foreground">
                {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, sortedStocks.length)} / {sortedStocks.length}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-1 rounded hover:bg-muted disabled:opacity-50"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="text-xs px-2">{page}/{totalPages}</span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="p-1 rounded hover:bg-muted disabled:opacity-50"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

// Main Dashboard Component
export function VolumeSpikeDashboard({ className }: VolumeSpikeDashboardProps) {
  const [minRatio, setMinRatio] = useState(1.5)
  const [exchange, setExchange] = useState<string>()
  const [includeUpcom, setIncludeUpcom] = useState(false)

  const { data, isLoading, isFetching, error, refetch } = useVolumeSpikes({
    minRatio,
    exchange,
    includeUpcom,
  })

  // Calculate summary stats
  const stats = useMemo(() => {
    if (!data?.industries?.length) return { avgRatio: 0, topIndustry: "" }
    const allStocks = data.industries.flatMap(g => g.stocks)
    const avgRatio = allStocks.length > 0
      ? allStocks.reduce((sum, s) => sum + s.spike_ratio, 0) / allStocks.length
      : 0
    const topIndustry = data.industries.reduce((max, g) =>
      g.spike_count > (max?.spike_count || 0) ? g : max, data.industries[0]
    )?.icb_name || ""
    return { avgRatio, topIndustry }
  }, [data])

  if (isLoading && !data) {
    return <VolumeSpikeDashboardSkeleton className={className} />
  }

  if (error) {
    return (
      <div className={cn("space-y-4", className)}>
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
          <p className="text-sm text-destructive">
            Không thể tải dữ liệu: {error.message}
          </p>
          <button onClick={() => refetch()} className="mt-2 text-sm underline hover:no-underline">
            Thử lại
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Khối lượng đột biến</h1>
          <p className="text-sm text-muted-foreground">
            {data?.trade_date || "N/A"} • {data?.total_spikes || 0} cổ phiếu
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="p-2 rounded-md hover:bg-muted transition-colors disabled:opacity-50 self-end"
          title="Làm mới"
        >
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <Label className="text-sm text-muted-foreground whitespace-nowrap">Ngưỡng:</Label>
          <Select value={String(minRatio)} onValueChange={(v) => setMinRatio(Number(v))}>
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
        <div className="flex items-center gap-2">
          <Label className="text-sm text-muted-foreground whitespace-nowrap">Sàn:</Label>
          <Select value={exchange || "all"} onValueChange={(v) => setExchange(v === "all" ? undefined : v)}>
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
        <div className="flex items-center gap-2">
          <Checkbox
            id="upcom"
            checked={includeUpcom}
            onCheckedChange={(checked) => setIncludeUpcom(checked === true)}
          />
          <Label htmlFor="upcom" className="text-sm cursor-pointer">UPCOM</Label>
        </div>
      </div>

      {/* Summary Cards */}
      <SummaryCards
        totalSpikes={data?.total_spikes || 0}
        avgRatio={stats.avgRatio}
        topIndustry={stats.topIndustry}
      />

      {/* Chart */}
      {data?.industries && data.industries.length > 0 && (
        <VolumeSpikeChart industries={data.industries} />
      )}

      {/* Industry Groups */}
      {data?.industries && data.industries.length > 0 ? (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Theo ngành ICB</h2>
          {data.industries
            .sort((a, b) => b.spike_count - a.spike_count)
            .map((group, idx) => (
              <IndustrySpikeGroup
                key={group.icb_code}
                group={group}
                defaultOpen={idx === 0}
              />
            ))}
        </div>
      ) : (
        <div className="rounded-lg border border-border/50 bg-card/50 p-8 text-center">
          <p className="text-muted-foreground">Không có cổ phiếu nào đạt ngưỡng đột biến.</p>
        </div>
      )}

      {/* Metadata */}
      {data?.metadata && (
        <p className="text-xs text-muted-foreground text-right">
          {data.metadata.symbols_processed} CP phân tích • {data.metadata.calculation_time_ms}ms
          {data.metadata.cache_hit && " • cached"}
        </p>
      )}
    </div>
  )
}

// Skeleton
export function VolumeSpikeDashboardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-6", className)}>
      <div className="flex justify-between">
        <div>
          <div className="h-8 w-48 bg-muted animate-pulse rounded" />
          <div className="h-4 w-32 bg-muted animate-pulse rounded mt-2" />
        </div>
        <div className="h-9 w-9 bg-muted animate-pulse rounded" />
      </div>
      <div className="flex gap-4">
        <div className="h-9 w-32 bg-muted animate-pulse rounded" />
        <div className="h-9 w-32 bg-muted animate-pulse rounded" />
        <div className="h-5 w-20 bg-muted animate-pulse rounded" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 bg-muted animate-pulse rounded-lg" />
        ))}
      </div>
      <div className="space-y-3">
        <div className="h-6 w-32 bg-muted animate-pulse rounded" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-12 bg-muted animate-pulse rounded-lg" />
        ))}
      </div>
    </div>
  )
}
