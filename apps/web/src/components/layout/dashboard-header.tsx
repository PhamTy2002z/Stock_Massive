"use client"

import { Search, Share2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { StockSearchBar } from "@/components/dashboard"
import { StockSymbol } from "@/lib/api"
import { NotificationPanel } from "./notification-panel"

interface DashboardHeaderProps {
  onStockSelect?: (symbol: string) => void
}

export function DashboardHeader({ onStockSelect }: DashboardHeaderProps) {
  const handleStockSelect = (stock: StockSymbol) => {
    if (onStockSelect) {
      onStockSelect(stock.symbol)
    }
  }

  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center justify-between border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4 transition-all duration-200">
      <div className="flex items-center gap-3">
        <div className="hidden md:block">
          <StockSearchBar
            onSelect={handleStockSelect}
            placeholder="Search stocks, markets..."
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Mobile search button */}
        <Button variant="ghost" size="icon" className="md:hidden">
          <Search className="h-5 w-5" />
          <span className="sr-only">Search</span>
        </Button>

        {/* Share */}
        <Button variant="ghost" size="icon">
          <Share2 className="h-5 w-5" />
          <span className="sr-only">Share</span>
        </Button>

        {/* Notifications - Job Status Panel */}
        <NotificationPanel />
      </div>
    </header>
  )
}
