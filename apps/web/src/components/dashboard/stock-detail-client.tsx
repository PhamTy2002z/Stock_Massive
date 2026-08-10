"use client"

import { Suspense, useState, useEffect } from "react"
import { toast } from "sonner"
import { useStockDetail } from "@/hooks/use-stock-detail"
import { getStockLoadingToastId, clearStockLoadingToast } from "./stock-search-bar"
import {
  StockTickerHeader,
  StockRangeCards,
  StockRangeCardsSkeleton,
  StockPriceChart,
  StockPriceChartSkeleton,
  StockValuationVsSector,
  StockValuationVsSectorSkeleton,
  StockProfileSidebar,
  StockProfileSidebarSkeleton,
  StockSnapshotPanel,
  StockSnapshotPanelSkeleton,
  StockTickerHeaderSkeleton,
  StockDetailEmpty,
  StockDetailTabs,
  StockDetailTabsSkeleton,
  FinanceTabContent,
  ShareholdersTabContent,
  VolumeTabContent,
  OrderFlowTabContent,
} from "@/components/dashboard"
import type { StockDetailTabValue } from "@/components/dashboard"

interface StockDetailClientProps {
  initialSymbol: string | null
}

/**
 * The identity bar and its tabs, pinned under the app header.
 *
 * Negative margins undo the page padding so the blur runs edge to edge, the
 * way a toolbar does — the content below scrolls under it rather than past it.
 */
function StickyBar({ children }: { children: React.ReactNode }) {
  return (
    <div className="sticky top-0 z-20 -mx-6 -mt-6 border-b border-border bg-background/80 px-6 pt-5 backdrop-blur-xl backdrop-saturate-150">
      {children}
    </div>
  )
}

// Loading fallback for Suspense
function StockDetailLoading() {
  return (
    <>
      <StickyBar>
        <StockTickerHeaderSkeleton />
        <StockDetailTabsSkeleton className="mt-3.5" />
      </StickyBar>
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-4">
          <StockPriceChartSkeleton />
          <StockRangeCardsSkeleton />
          <StockValuationVsSectorSkeleton />
        </div>
        <StockProfileSidebarSkeleton />
      </section>
    </>
  )
}

// Inner component that uses the hook - only rendered when symbol is valid
function StockDetailInner({ symbol }: { symbol: string }) {
  const [activeTab, setActiveTab] = useState<StockDetailTabValue>("overview")
  const { data, dataUpdatedAt, isFetching, refetch } = useStockDetail(symbol)

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
      <StickyBar>
        <StockTickerHeader
          symbol={data.symbol}
          companyName={data.company_name || data.symbol}
          price={data.price || 0}
          change={data.change || 0}
          changePercent={data.change_pct || 0}
          ceiling={data.ceiling}
          floor={data.floor}
          refPrice={data.ref_price}
          onRefresh={() => void refetch()}
          isRefreshing={isFetching}
          updatedAt={dataUpdatedAt}
        />
        <StockDetailTabs value={activeTab} onChange={setActiveTab} className="mt-3.5" />
      </StickyBar>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        {/* Left: Main Content */}
        <div className="space-y-4">
          <div className="stock-detail-enter">
            {activeTab === "overview" && (
              <div className="space-y-4">
                <StockPriceChart symbol={data.symbol} refPrice={data.ref_price} />
                <StockRangeCards
                  price={data.price}
                  openPrice={data.open_price}
                  lowPrice={data.low_price}
                  highPrice={data.high_price}
                  low52Week={data.low_52_week}
                  high52Week={data.high_52_week}
                  volume={data.volume}
                  tradingValue={data.trading_value}
                  avgVolume52Week={data.avg_volume_52_week}
                />
                <Suspense fallback={<StockValuationVsSectorSkeleton />}>
                  <StockValuationVsSector symbol={data.symbol} />
                </Suspense>
                {/* Last, because it is the only block that dates its numbers:
                    read after the live figures above, it says which session
                    this system actually holds for the symbol. */}
                <Suspense fallback={<StockSnapshotPanelSkeleton />}>
                  <StockSnapshotPanel symbol={data.symbol} />
                </Suspense>
              </div>
            )}

            {activeTab === "orderflow" && <OrderFlowTabContent symbol={data.symbol} />}

            {activeTab === "finance" && <FinanceTabContent symbol={data.symbol} />}
            {activeTab === "shareholders" && <ShareholdersTabContent symbol={data.symbol} />}
            {activeTab === "volume" && <VolumeTabContent symbol={data.symbol} />}
          </div>
        </div>

        {/* Right: reference column — profile and sector peers */}
        <Suspense fallback={<StockProfileSidebarSkeleton />}>
          <StockProfileSidebar stock={data} />
        </Suspense>
      </section>
    </>
  )
}

export function StockDetailClient({ initialSymbol }: StockDetailClientProps) {
  // No symbol - show empty state
  if (!initialSymbol) {
    return (
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-4">
          <StockDetailEmpty />
        </div>
        <div className="space-y-4" />
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
