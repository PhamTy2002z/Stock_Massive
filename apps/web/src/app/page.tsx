import { Suspense } from "react"
import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import {
  MarketIndices,
  MarketIndicesSkeleton,
  SectorPerformanceSection,
  FundCertificates,
  VN30OverviewTable,
  VN30OverviewTableSkeleton,
} from "@/components/dashboard"
import {
  fetchMarketIndicesServer,
  fetchSectorPerformanceServer,
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
  ])

  return dehydrate(queryClient)
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-8">
      <MarketIndicesSkeleton />
      <VN30OverviewTableSkeleton />
    </div>
  )
}

export default async function Home() {
  const dehydratedState = await prefetchData()

  return (
    <HydrationBoundary state={dehydratedState}>
      <Suspense fallback={<DashboardLayoutClient><DashboardSkeleton /></DashboardLayoutClient>}>
        <DashboardLayoutClient>
          <div className="flex min-w-0 flex-col gap-8">
            <MarketIndices />

            <VN30OverviewTable />

            {/* Sector extremes and funds share one row: three readings of the
                same session, each answering a different question. */}
            <div className="grid min-w-0 grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-3.5">
              <SectorPerformanceSection />
              <FundCertificates />
            </div>

            <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-4 text-xs leading-[1.6] tracking-[-0.12px] text-muted-foreground">
              <span>
                Dữ liệu chỉ mang tính tham khảo, không phải khuyến nghị đầu tư. Nguồn: HOSE,
                HNX, UPCoM.
              </span>
              <span>© {new Date().getFullYear()} Stock Massive</span>
            </footer>
          </div>
        </DashboardLayoutClient>
      </Suspense>
    </HydrationBoundary>
  )
}
