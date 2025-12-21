import { Suspense } from "react"
import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import {
  MarketIndices,
  SectorPerformance,
  FundCertificates,
  VN30OverviewTable,
  StockTickerHeaderSkeleton,
  StockDetailTabsSkeleton,
  StockDetailPanelSkeleton,
  StockStatsTableSkeleton,
  StockCompanyInfoSkeleton,
  StockDetailClient,
} from "@/components/dashboard"
import { fetchMarketIndicesServer, fetchSectorPerformanceServer, fetchStockDetailServer } from "@/lib/api-server"
import { queryKeys } from "@/lib/query-keys"

const DEFAULT_SYMBOL = "VCB"

interface HomeProps {
  searchParams: Promise<{ symbol?: string }>
}

async function prefetchData(symbol: string) {
  const queryClient = new QueryClient()

  // Prefetch all three in parallel
  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: queryKeys.marketIndices,
      queryFn: fetchMarketIndicesServer,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.sectorPerformance,
      queryFn: fetchSectorPerformanceServer,
    }),
    symbol
      ? queryClient.prefetchQuery({
          queryKey: queryKeys.stockDetail(symbol),
          queryFn: () => fetchStockDetailServer(symbol),
        })
      : Promise.resolve(),
  ])

  return dehydrate(queryClient)
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <section>
        <h2 className="text-lg font-semibold text-foreground mb-4">
          Chỉ số thị trường
        </h2>
        <MarketIndices />
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
  )
}

export default async function Home({ searchParams }: HomeProps) {
  const params = await searchParams
  const symbol = params.symbol || DEFAULT_SYMBOL
  const dehydratedState = await prefetchData(symbol)

  return (
    <HydrationBoundary state={dehydratedState}>
      <Suspense fallback={<DashboardLayoutClient><DashboardSkeleton /></DashboardLayoutClient>}>
        <DashboardLayoutClient>
          <div className="flex flex-col gap-6">
            {/* Market Indices Section */}
            <section>
              <h2 className="text-lg font-semibold text-foreground mb-4">
                Chỉ số thị trường
              </h2>
              <MarketIndices />
            </section>

            {/* VN30 Overview Section */}
            <section>
              <h2 className="text-lg font-semibold text-foreground mb-4">
                Tổng quan VN30
              </h2>
              <VN30OverviewTable />
            </section>

            {/* Selected Stock Detail */}
            <StockDetailClient initialSymbol={symbol} />

            {/* Sector Performance & Fund Certificates */}
            <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
              <div>
                <h2 className="text-lg font-semibold text-foreground mb-4">
                  Hiệu suất ngành
                </h2>
                <SectorPerformance />
              </div>

              <div>
                <h2 className="text-lg font-semibold text-foreground mb-4">
                  Chứng chỉ quỹ
                </h2>
                <FundCertificates />
              </div>
            </section>
          </div>
        </DashboardLayoutClient>
      </Suspense>
    </HydrationBoundary>
  )
}
