"use client"

import { Suspense, useState, useEffect } from "react"
import { toast } from "sonner"
import { useStockDetail } from "@/hooks/use-stock-detail"
import { getStockLoadingToastId, clearStockLoadingToast } from "./stock-search-bar"
import {
  StockTickerHeader,
  StockDetailPanel,
  StockStatsTable,
  StockCompanyInfo,
  StockTickerHeaderSkeleton,
  StockDetailPanelSkeleton,
  StockStatsTableSkeleton,
  StockCompanyInfoSkeleton,
  StockDetailEmpty,
  StockDetailTabs,
  StockDetailTabsSkeleton,
  FinanceTabContent,
  ShareholdersTabContent,
  VolumeTabContent,
  AdvancedSection,
  AdvancedSectionSkeleton,
} from "@/components/dashboard"
import type { StockDetailTabValue } from "@/components/dashboard"

interface StockDetailClientProps {
  initialSymbol: string | null
}

// Loading fallback for Suspense
function StockDetailLoading() {
  return (
    <>
      <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        <div className="space-y-4">
          <StockTickerHeaderSkeleton />
          <StockDetailTabsSkeleton className="mt-2" />
          <StockDetailPanelSkeleton />
          <StockStatsTableSkeleton />
        </div>
        <div className="space-y-4 lg:pt-6">
          <StockCompanyInfoSkeleton />
        </div>
      </section>
      <AdvancedSectionSkeleton />
    </>
  )
}

// Inner component that uses the hook - only rendered when symbol is valid
function StockDetailInner({ symbol }: { symbol: string }) {
  const [activeTab, setActiveTab] = useState<StockDetailTabValue>("overview")
  const { data } = useStockDetail(symbol)

  // Update loading toast when data loads
  useEffect(() => {
    const toastId = getStockLoadingToastId()
    if (!toastId) return

    if (data) {
      toast.success(`${data.symbol} loaded`, {
        id: toastId,
        description: data.company_name || "Stock data ready",
      })
      clearStockLoadingToast()
    }
  }, [data])

  return (
    <>
      <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        {/* Left: Main Content */}
        <div className="space-y-4">
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

            {activeTab === "overview" && (
              <div className="space-y-4">
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
                  high52Week={data.high_52_week}
                  low52Week={data.low_52_week}
                  avgVolume52Week={data.avg_volume_52_week}
                  eps={data.eps}
                  pe={data.pe}
                  pb={data.pb}
                  dividendYield={data.dividend_yield}
                />
              </div>
            )}

            {activeTab === "finance" && <FinanceTabContent symbol={data.symbol} />}
            {activeTab === "shareholders" && <ShareholdersTabContent symbol={data.symbol} />}
            {activeTab === "volume" && <VolumeTabContent symbol={data.symbol} />}
          </div>
        </div>

        {/* Right: Company Info Sidebar */}
        <div className="space-y-4 lg:pt-6">
          <StockCompanyInfo
            symbol={data.symbol}
            industry={data.industry || "N/A"}
            marketCap={data.market_cap || 0}
            outstandingShares={(data.outstanding_shares || 0) / 1_000_000_000}
            exchange={data.exchange}
            vn30Rank={data.vn30_rank}
            description={data.description || "No description available."}
          />
        </div>
      </section>

      {/* Advanced Analysis Section - Below Stock Detail */}
      <AdvancedSection symbol={data.symbol} className="stock-detail-enter" />
    </>
  )
}

export function StockDetailClient({ initialSymbol }: StockDetailClientProps) {
  // No symbol - show empty state
  if (!initialSymbol) {
    return (
      <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        <div className="space-y-4">
          <StockDetailEmpty />
        </div>
        <div className="space-y-4 lg:pt-6" />
      </section>
    )
  }

  // Valid symbol - render with Suspense
  return (
    <Suspense fallback={<StockDetailLoading />}>
      <StockDetailInner symbol={initialSymbol} />
    </Suspense>
  )
}
