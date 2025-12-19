"use client"

import { useState, useEffect, Suspense } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/layout"
import {
  MarketIndices,
  StockTickerHeader,
  StockDetailPanel,
  StockStatsTable,
  StockCompanyInfo,
  StockTickerHeaderSkeleton,
  StockDetailPanelSkeleton,
  StockStatsTableSkeleton,
  StockCompanyInfoSkeleton,
  StockDetailError,
  StockDetailEmpty,
  StockDetailTabs,
  StockDetailTabsSkeleton,
  FinanceTabContent,
  FinanceTabContentSkeleton,
  ShareholdersTabContent,
  ShareholdersTabContentSkeleton,
  SectorPerformance,
} from "@/components/dashboard"
import type { StockDetailTabValue } from "@/components/dashboard"
import { useStockDetail } from "@/hooks/use-stock-detail"

const DEFAULT_SYMBOL = "VCB"

function HomeContent() {
  const searchParams = useSearchParams()
  const router = useRouter()

  // Initialize from URL or default to VCB
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(() => {
    return searchParams.get("symbol") || DEFAULT_SYMBOL
  })

  // Active tab state for stock detail tabs
  const [activeTab, setActiveTab] = useState<StockDetailTabValue>("overview")

  const { data, isLoading, error, refetch } = useStockDetail(selectedSymbol)

  // Update URL when symbol changes
  const handleStockSelect = (symbol: string) => {
    setSelectedSymbol(symbol)
    const params = new URLSearchParams(searchParams.toString())
    params.set("symbol", symbol)
    router.push(`/?${params.toString()}`, { scroll: false })
  }

  // Sync URL changes back to state (browser back/forward)
  useEffect(() => {
    const urlSymbol = searchParams.get("symbol")
    if (urlSymbol) {
      setSelectedSymbol((prev) => (urlSymbol !== prev ? urlSymbol : prev))
    }
  }, [searchParams])

  return (
    <DashboardLayout onStockSelect={handleStockSelect}>
      <div className="flex flex-col gap-6">
        {/* Market Indices Section */}
        <section>
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Chỉ số thị trường
          </h2>
          <MarketIndices />
        </section>

        {/* Sector Performance Section */}
        <section>
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Hiệu suất ngành
          </h2>
          <SectorPerformance />
        </section>

        {/* Selected Stock Detail */}
        <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
          {/* Left: Main Content */}
          <div className="space-y-4">
            {/* Error State */}
            {error && <StockDetailError error={error} onRetry={refetch} />}

            {/* Loading State */}
            {isLoading && (
              <>
                <StockTickerHeaderSkeleton />
                <StockDetailTabsSkeleton className="mt-2" />
                <StockDetailPanelSkeleton />
                <StockStatsTableSkeleton />
              </>
            )}

            {/* Empty State */}
            {!selectedSymbol && !isLoading && !error && <StockDetailEmpty />}

            {/* Data State */}
            {!isLoading && !error && data && (
              <div className="stock-detail-enter">
                <StockTickerHeader
                  symbol={data.symbol}
                  companyName={data.company_name || data.symbol}
                  price={data.price || 0}
                  change={data.change || 0}
                  changePercent={data.change_pct || 0}
                />
                <StockDetailTabs
                  value={activeTab}
                  onChange={setActiveTab}
                  className="mt-2 mb-4"
                />

                {/* Tab Content - Overview */}
                {activeTab === "overview" && (
                  <>
                    <StockDetailPanel
                      volume={data.volume || 0}
                      exchange={data.exchange || "N/A"}
                      marketCap={data.market_cap || 0}
                      industry={data.industry || "N/A"}
                    />
                    <StockStatsTable
                      openPrice={data.open_price || data.ref_price || 0}
                      highPrice={data.high_price || 0}
                      lowPrice={data.low_price || 0}
                      tradingVolume={data.volume || 0}
                      marketCap={data.market_cap || 0}
                      high52Week={data.high_52_week || 0}
                      low52Week={data.low_52_week || 0}
                      avgVolume52Week={data.avg_volume_52_week || 0}
                      eps={data.eps}
                      pe={data.pe}
                      beta={data.beta}
                      dividendYield={data.dividend_yield}
                    />
                  </>
                )}

                {/* Tab Content - Finance */}
                {activeTab === "finance" && (
                  <FinanceTabContent symbol={data.symbol} />
                )}

                {/* Tab Content - Shareholders */}
                {activeTab === "shareholders" && (
                  <ShareholdersTabContent symbol={data.symbol} />
                )}
              </div>
            )}
          </div>

          {/* Right: Company Info Sidebar */}
          <div className="space-y-4">
            {isLoading && <StockCompanyInfoSkeleton />}
            {!isLoading && !error && data && (
              <StockCompanyInfo
                symbol={data.symbol}
                industry={data.industry || "N/A"}
                marketCap={data.market_cap || 0}
                outstandingShares={(data.outstanding_shares || 0) / 1_000_000_000}
                exchange={data.exchange}
                vn30Rank={null}
                description={data.description || "No description available."}
              />
            )}
          </div>
        </section>
      </div>
    </DashboardLayout>
  )
}

// Wrap with Suspense for useSearchParams
export default function Home() {
  return (
    <Suspense fallback={
      <DashboardLayout>
        <div className="flex flex-col gap-6">
          <section>
            <h2 className="text-lg font-semibold text-foreground mb-4">
              Chỉ số thị trường
            </h2>
            <MarketIndices />
          </section>
          <section>
            <h2 className="text-lg font-semibold text-foreground mb-4">
              Hiệu suất ngành
            </h2>
            <SectorPerformance />
          </section>
          <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
            <div className="space-y-4">
              <StockTickerHeaderSkeleton />
              <StockDetailTabsSkeleton className="mt-2" />
              <StockDetailPanelSkeleton />
              <StockStatsTableSkeleton />
            </div>
            <div className="space-y-4">
              <StockCompanyInfoSkeleton />
            </div>
          </section>
        </div>
      </DashboardLayout>
    }>
      <HomeContent />
    </Suspense>
  )
}
