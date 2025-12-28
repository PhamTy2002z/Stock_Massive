"use client"

import { useState, useEffect } from "react"
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
  StockDetailError,
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

export function StockDetailClient({ initialSymbol }: StockDetailClientProps) {
  const [activeTab, setActiveTab] = useState<StockDetailTabValue>("overview")
  const { data, isLoading, error, refetch } = useStockDetail(initialSymbol)

  // Update loading toast when data loads or errors
  useEffect(() => {
    const toastId = getStockLoadingToastId()
    if (!toastId) return

    // Dismiss toast when loading completes (success or error)
    if (!isLoading) {
      if (data) {
        toast.success(`${data.symbol} loaded`, {
          id: toastId,
          description: data.company_name || "Stock data ready",
        })
        clearStockLoadingToast()
      } else if (error) {
        toast.error("Failed to load stock", {
          id: toastId,
          description: error.message || "Please try again",
        })
        clearStockLoadingToast()
      }
    }
  }, [isLoading, data, error])

  return (
    <>
    <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
      {/* Left: Main Content */}
      <div className="space-y-4">
        {error && <StockDetailError error={error} onRetry={refetch} />}

        {isLoading && (
          <>
            <StockTickerHeaderSkeleton />
            <StockDetailTabsSkeleton className="mt-2" />
            <StockDetailPanelSkeleton />
            <StockStatsTableSkeleton />
          </>
        )}

        {!initialSymbol && !isLoading && !error && <StockDetailEmpty />}

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
                  high52Week={data.high_52_week || 0}
                  low52Week={data.low_52_week || 0}
                  avgVolume52Week={data.avg_volume_52_week || 0}
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
        )}
      </div>

      {/* Right: Company Info Sidebar */}
      <div className="space-y-4 lg:pt-6">
        {isLoading && <StockCompanyInfoSkeleton />}
        {!isLoading && !error && data && (
          <StockCompanyInfo
            symbol={data.symbol}
            industry={data.industry || "N/A"}
            marketCap={data.market_cap || 0}
            outstandingShares={(data.outstanding_shares || 0) / 1_000_000_000}
            exchange={data.exchange}
            vn30Rank={data.vn30_rank}
            description={data.description || "No description available."}
          />
        )}
      </div>
    </section>

    {/* Advanced Analysis Section - Below Stock Detail */}
    {isLoading && <AdvancedSectionSkeleton />}
    {!isLoading && !error && data && (
      <AdvancedSection symbol={data.symbol} className="stock-detail-enter" />
    )}
  </>
  )
}
