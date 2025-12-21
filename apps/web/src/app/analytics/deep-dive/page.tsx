import { Suspense } from "react"
import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import {
  StockTickerHeaderSkeleton,
  StockDetailTabsSkeleton,
  StockDetailPanelSkeleton,
  StockStatsTableSkeleton,
  StockCompanyInfoSkeleton,
  StockDetailClient,
} from "@/components/dashboard"
import { fetchStockDetailServer } from "@/lib/api-server"
import { queryKeys } from "@/lib/query-keys"

const DEFAULT_SYMBOL = "VCB"

interface DeepDivePageProps {
  searchParams: Promise<{ symbol?: string }>
}

async function prefetchData(symbol: string) {
  const queryClient = new QueryClient()

  if (symbol) {
    await queryClient.prefetchQuery({
      queryKey: queryKeys.stockDetail(symbol),
      queryFn: () => fetchStockDetailServer(symbol),
    })
  }

  return dehydrate(queryClient)
}

function DeepDiveSkeleton() {
  return (
    <div className="flex flex-col gap-6">
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

export default async function DeepDivePage({ searchParams }: DeepDivePageProps) {
  const params = await searchParams
  const symbol = params.symbol || DEFAULT_SYMBOL
  const dehydratedState = await prefetchData(symbol)

  return (
    <HydrationBoundary state={dehydratedState}>
      <Suspense fallback={<DashboardLayoutClient><DeepDiveSkeleton /></DashboardLayoutClient>}>
        <DashboardLayoutClient>
          <div className="flex flex-col gap-6">
            {/* Selected Stock Detail */}
            <StockDetailClient initialSymbol={symbol} />
          </div>
        </DashboardLayoutClient>
      </Suspense>
    </HydrationBoundary>
  )
}
