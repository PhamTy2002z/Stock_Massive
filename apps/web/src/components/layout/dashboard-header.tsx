"use client"

import Link from "next/link"
import { Search, Share2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { StockSearchBar } from "@/components/dashboard"
import { StockSymbol } from "@/lib/api"
import { NotificationPanel } from "./notification-panel"

interface DashboardHeaderProps {
  onStockSelect?: (symbol: string) => void
}

/**
 * Full-width bar above the sidebar. The logo cell is exactly one rail wide so
 * the mark sits directly above the nav icons, the way Supabase anchors theirs.
 * Kept in sync by hand with SIDEBAR_WIDTH_ICON: --sidebar-width-icon is scoped
 * to SidebarProvider, which lives below this bar.
 */
export function DashboardHeader({ onStockSelect }: DashboardHeaderProps) {
  const handleStockSelect = (stock: StockSymbol) => {
    if (onStockSelect) {
      onStockSelect(stock.symbol)
    }
  }

  return (
    <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center border-b border-sidebar-border bg-sidebar">
      <Link
        href="/"
        aria-label="Stock Massive"
        className="flex h-full w-12 shrink-0 items-center justify-center"
      >
        <img src="/logo.png" alt="Stock Massive" className="size-7 object-contain" />
      </Link>

      <div className="flex flex-1 items-center gap-3 pl-3">
        <div className="hidden md:block">
          <StockSearchBar
            onSelect={handleStockSelect}
            placeholder="Search stocks, markets..."
          />
        </div>
      </div>

      <div className="flex items-center gap-2 pr-3">
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
