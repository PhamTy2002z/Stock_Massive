"use client"

import { Search } from "lucide-react"

export function StockDetailEmpty() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="rounded-full bg-muted p-4 mb-4">
        <Search className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">
        No Stock Selected
      </h3>
      <p className="text-sm text-muted-foreground max-w-sm">
        Search for a stock symbol using the search bar above to view detailed information.
      </p>
    </div>
  )
}
