import { Suspense } from "react"
import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import {
  MarketIndices,
  SectorPerformanceSection,
  FundCertificates,
  VN30OverviewTable,
  CollapsibleSection,
  MarketBreadth,
  TopMovers,
  ForeignFlow,
} from "@/components/dashboard"
import {
  MarketBreadthSkeleton,
  TopMoversSkeleton,
  ForeignFlowSkeleton,
} from "@/components/dashboard/market-overview-skeleton"
import {
  fetchMarketIndicesServer,
  fetchSectorPerformanceServer,
  fetchMarketOverviewServer,
} from "@/lib/api-server"
import { queryKeys } from "@/lib/query-keys"

async function prefetchData() {
  const queryClient = new QueryClient()

  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: queryKeys.marketIndices,
      queryFn: fetchMarketIndicesServer,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.sectorPerformance,
      queryFn: fetchSectorPerformanceServer,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.marketOverview,
      queryFn: fetchMarketOverviewServer,
    }),
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
    </div>
  )
}

export default async function Home() {
  const dehydratedState = await prefetchData()

  return (
    <HydrationBoundary state={dehydratedState}>
      <Suspense fallback={<DashboardLayoutClient><DashboardSkeleton /></DashboardLayoutClient>}>
        <DashboardLayoutClient>
          <div className="flex flex-col gap-6">
            {/* Market Indices Section */}
            <section>
              <MarketIndices />
            </section>

            {/* Market Breadth Section */}
            <CollapsibleSection id="market-breadth" title="Độ rộng thị trường">
              <Suspense fallback={<MarketBreadthSkeleton />}>
                <MarketBreadth />
              </Suspense>
            </CollapsibleSection>

            {/* Top Movers + Foreign Flow Grid */}
            <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <CollapsibleSection id="top-movers" title="Top Biến động">
                <Suspense fallback={<TopMoversSkeleton />}>
                  <TopMovers />
                </Suspense>
              </CollapsibleSection>

              <CollapsibleSection id="foreign-flow" title="Giao dịch NDNN">
                <Suspense fallback={<ForeignFlowSkeleton />}>
                  <ForeignFlow />
                </Suspense>
              </CollapsibleSection>
            </section>

            {/* VN30 Overview Section */}
            <section>
              <VN30OverviewTable />
            </section>

            {/* Sector Performance & Fund Certificates */}
            <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
              <SectorPerformanceSection />
              <FundCertificates />
            </section>
          </div>
        </DashboardLayoutClient>
      </Suspense>
    </HydrationBoundary>
  )
}
