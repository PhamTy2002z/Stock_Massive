"use client"

import Link from "next/link"
import { Search, Share2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { StockSearchBar } from "@/components/dashboard"
import { StockSymbol } from "@/lib/api"
import { NotificationPanel } from "./notification-panel"
import { UserMenu } from "./user-menu"

interface DashboardHeaderProps {
  onStockSelect?: (symbol: string) => void
}

/**
 * Full-width bar above the sidebar: 64px, white, one hairline underneath.
 * The mark and wordmark lead, search sits immediately beside them rather than
 * floating in the middle, and the account block anchors the right edge.
 */
export function DashboardHeader({ onStockSelect }: DashboardHeaderProps) {
  const handleStockSelect = (stock: StockSymbol) => {
    if (onStockSelect) {
      onStockSelect(stock.symbol)
    }
  }

  return (
    <header className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-5 border-b border-border bg-card px-5">
      <Link
        href="/"
        aria-label="Stock Massive"
        className="flex shrink-0 items-center gap-[9px]"
      >
        <img src="/logo.png" alt="" className="size-[22px] object-contain" />
        <span className="text-[15px] font-semibold leading-[1.24] tracking-[-0.374px]">
          Stock Massive
        </span>
      </Link>

      {/* Grows with the header up to the design's 420px ceiling. */}
      <div className="hidden max-w-[420px] flex-1 md:block">
        <StockSearchBar
          onSelect={handleStockSelect}
          placeholder="Tìm mã, ngành, chỉ số"
        />
      </div>

      <div className="flex-1" />

      <div className="flex items-center gap-1.5">
        {/* Mobile search button */}
        <Button variant="ghost" size="icon" className="size-9 rounded-full md:hidden">
          <Search className="size-[17px]" />
          <span className="sr-only">Tìm kiếm</span>
        </Button>

        {/* Share */}
        <Button variant="ghost" size="icon" className="size-9 rounded-full">
          <Share2 className="size-[17px]" />
          <span className="sr-only">Chia sẻ</span>
        </Button>

        {/* Notifications - Job Status Panel */}
        <NotificationPanel />

        <UserMenu />
      </div>
    </header>
  )
}
