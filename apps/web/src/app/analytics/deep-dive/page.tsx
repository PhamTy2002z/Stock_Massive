import { Suspense } from "react"
import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import {
  StockTickerHeaderSkeleton,
  StockDetailTabsSkeleton,
  StockPriceChartSkeleton,
  StockRangeCardsSkeleton,
  StockValuationVsSectorSkeleton,
  StockProfileSidebarSkeleton,
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
      <section className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_280px] gap-4">
        <div className="space-y-4">
          <StockTickerHeaderSkeleton />
          <StockDetailTabsSkeleton className="mt-2" />
          <StockPriceChartSkeleton />
          <StockRangeCardsSkeleton />
          <StockValuationVsSectorSkeleton />
        </div>
        <div className="space-y-4">
          <StockProfileSidebarSkeleton />
        </div>
      </section>
    </div>
  )
}

/**
 * Holds the await so the page shell can stream ahead of it.
 *
 * The prefetch used to run in the page body, before any Suspense boundary —
 * Next.js sends no HTML at all until such an await resolves, so a slow /detail
 * call left the browser on a blank page rather than the skeleton below.
 */
async function DeepDiveContent({ symbol }: { symbol: string }) {
  const dehydratedState = await prefetchData(symbol)

  return (
    <HydrationBoundary state={dehydratedState}>
      <div className="flex flex-col gap-6">
        {/* Selected Stock Detail */}
        <StockDetailClient initialSymbol={symbol} />
      </div>
    </HydrationBoundary>
  )
}

export default async function DeepDivePage({ searchParams }: DeepDivePageProps) {
  const params = await searchParams
  const symbol = params.symbol || DEFAULT_SYMBOL

  return (
    <DashboardLayoutClient>
      <Suspense fallback={<DeepDiveSkeleton />}>
        <DeepDiveContent symbol={symbol} />
      </Suspense>
    </DashboardLayoutClient>
  )
}
