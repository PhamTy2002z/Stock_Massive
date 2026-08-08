"use client"

import { useState, useMemo, useEffect } from "react"
import { cn } from "@/lib/utils"
import { RefreshCw } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useVolumeSpikes } from "@/hooks/use-volume-spikes"
import { SummaryCards } from "./summary-cards"
import { SpikeChartTabs } from "./chart-tabs"
import { TopVolatilityTable } from "./top-volatility-table"
import { SectorGroupHeader, type SectorSortType } from "./sector-group-header"
import { IndustrySpikeGroup } from "./industry-spike-group"

interface VolumeSpikeDashboardProps {
  className?: string
}

// Main Dashboard Component
export function VolumeSpikeDashboard({ className }: VolumeSpikeDashboardProps) {
  // Data source tab state (Top 50 LN or All)
  const [dataSource, setDataSource] = useState<"top50" | "all">("top50")
  const topProfitableOnly = dataSource === "top50"

  const [minRatio, setMinRatio] = useState(1.5)
  const [exchange, setExchange] = useState<string>()
  const [includeUpcom, setIncludeUpcom] = useState(false)

  // ICB Sector UI state
  const [expandedSectors, setExpandedSectors] = useState<Set<string>>(new Set())
  const [sectorSort, setSectorSort] = useState<SectorSortType>("spike_count")
  const [selectedSector, setSelectedSector] = useState<string>("all")
  const [expandAll, setExpandAll] = useState(false)

  // data is ALWAYS defined with useSuspenseQuery - Suspense handles loading, ErrorBoundary handles errors
  const { data, isFetching, refetch } = useVolumeSpikes({
    minRatio,
    exchange: topProfitableOnly ? undefined : exchange,
    includeUpcom: topProfitableOnly ? false : includeUpcom,
    topProfitableOnly,
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

  // Sorted and filtered industries
  const sortedIndustries = useMemo(() => {
    if (!data?.industries) return []

    let filtered = data.industries
    if (selectedSector !== "all") {
      filtered = filtered.filter((g) => g.icb_code === selectedSector)
    }

    return [...filtered].sort((a, b) => {
      switch (sectorSort) {
        case "spike_count":
          return b.spike_count - a.spike_count
        case "avg_spike_ratio":
          return b.avg_spike_ratio - a.avg_spike_ratio
        case "name":
          return a.icb_name.localeCompare(b.icb_name, "vi")
        default:
          return 0
      }
    })
  }, [data?.industries, sectorSort, selectedSector])

  // All sectors for filter dropdown
  const allSectors = useMemo(() => {
    if (!data?.industries) return []
    return data.industries
      .map((g) => ({ code: g.icb_code, name: g.icb_name }))
      .sort((a, b) => a.name.localeCompare(b.name, "vi"))
  }, [data?.industries])

  // Flatten all stocks for ranking table
  const allStocks = useMemo(() => {
    if (!data?.industries) return []
    return data.industries.flatMap(g => g.stocks)
  }, [data?.industries])

  // Expand all toggle handler
  const handleExpandAllToggle = () => {
    if (expandAll) {
      setExpandedSectors(new Set())
    } else {
      setExpandedSectors(new Set(sortedIndustries.map((g) => g.icb_code)))
    }
    setExpandAll(!expandAll)
  }

  // Individual sector toggle handler
  const handleSectorToggle = (icbCode: string) => {
    setExpandedSectors((prev) => {
      const next = new Set(prev)
      if (next.has(icbCode)) {
        next.delete(icbCode)
      } else {
        next.add(icbCode)
      }
      return next
    })
  }

  // Initialize first sector as expanded when data loads
  useEffect(() => {
    if (data?.industries?.length && expandedSectors.size === 0 && !expandAll) {
      const firstCode = [...data.industries].sort((a, b) => b.spike_count - a.spike_count)[0]?.icb_code
      if (firstCode) {
        setExpandedSectors(new Set([firstCode]))
      }
    }
  }, [data?.industries, expandedSectors.size, expandAll])

  // data is always defined with useSuspenseQuery
  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">
            {topProfitableOnly
              ? "Khối lượng đột biến - Top 50 Lợi nhuận"
              : "Khối lượng đột biến"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {data?.trade_date || "N/A"} • {data?.total_spikes || 0} cổ phiếu
            {topProfitableOnly && " • Chỉ hiển thị CP từ 50 công ty có lợi nhuận cao nhất"}
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

      {/* Data Source Tabs */}
      <Tabs value={dataSource} onValueChange={(v) => setDataSource(v as "top50" | "all")}>
        <TabsList>
          <TabsTrigger value="top50">Top 50 LN</TabsTrigger>
          <TabsTrigger value="all">Tất cả</TabsTrigger>
        </TabsList>
      </Tabs>

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
        {/* Exchange filter - only show in "all" mode */}
        {!topProfitableOnly && (
          <>
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
          </>
        )}
      </div>

      {/* Summary Cards */}
      <SummaryCards
        totalSpikes={data?.total_spikes || 0}
        avgRatio={stats.avgRatio}
        topIndustry={stats.topIndustry}
      />

      {/* Charts with Tabs */}
      {data?.industries && data.industries.length > 0 && (
        <SpikeChartTabs industries={data.industries} />
      )}

      {/* Top Volatility Ranking Table */}
      {data?.industries && data.industries.length > 0 && (
        <TopVolatilityTable stocks={allStocks} />
      )}

      {/* Industry Groups */}
      {data?.industries && data.industries.length > 0 ? (
        <div className="space-y-3">
          <SectorGroupHeader
            sectorCount={sortedIndustries.length}
            sectorSort={sectorSort}
            onSortChange={setSectorSort}
            selectedSector={selectedSector}
            onSectorFilterChange={setSelectedSector}
            allSectors={allSectors}
            expandAll={expandAll}
            onExpandAllToggle={handleExpandAllToggle}
          />
          {sortedIndustries.length > 0 ? (
            sortedIndustries.map((group) => (
              <IndustrySpikeGroup
                key={group.icb_code}
                group={group}
                isOpen={expandedSectors.has(group.icb_code)}
                onToggle={() => handleSectorToggle(group.icb_code)}
              />
            ))
          ) : (
            <div className="rounded-lg border border-border/50 bg-card/50 p-8 text-center">
              <p className="text-muted-foreground">Không có ngành nào phù hợp với bộ lọc.</p>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-lg border border-border/50 bg-card/50 p-8 text-center">
          <p className="text-muted-foreground">
            {topProfitableOnly
              ? "Không có cổ phiếu Top 50 nào đạt ngưỡng đột biến hôm nay."
              : "Không có cổ phiếu nào đạt ngưỡng đột biến."}
          </p>
          {topProfitableOnly && (
            <Button
              variant="link"
              className="mt-2"
              onClick={() => setDataSource("all")}
            >
              Xem tab &quot;Tất cả&quot; để xem toàn bộ thị trường
            </Button>
          )}
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
