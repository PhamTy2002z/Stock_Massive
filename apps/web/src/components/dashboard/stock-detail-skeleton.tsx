"use client"

import { Skeleton } from "@/components/ui/skeleton"

export function StockTickerHeaderSkeleton() {
  return (
    <div className="py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="mt-2 h-4 w-20" />
        </div>
        <div className="text-right shrink-0">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="mt-2 h-4 w-32" />
        </div>
      </div>
    </div>
  )
}

export function StockDetailPanelSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="rounded-lg border bg-card p-3">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="mt-2 h-4 w-20" />
        </div>
      ))}
    </div>
  )
}

export function StockStatsTableSkeleton() {
  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border">
        {[1, 2, 3].map((col) => (
          <div key={col} className="divide-y divide-border">
            {[1, 2, 3, 4].map((row) => (
              <div key={row} className="flex items-center justify-between px-5 py-3.5">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-24" />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export function StockCompanyInfoSkeleton() {
  return (
    <div className="rounded-lg border bg-card">
      <div className="divide-y divide-border">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="flex items-center justify-between px-4 py-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-32" />
          </div>
        ))}
      </div>
      <div className="p-4 border-t border-border">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="mt-2 h-4 w-full" />
        <Skeleton className="mt-2 h-4 w-3/4" />
      </div>
    </div>
  )
}
