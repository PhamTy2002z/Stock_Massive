"use client"

import Link from "next/link"
import { MoreHorizontal, Search, Share2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { StockSearchBar } from "@/components/dashboard"
import { StockSymbol } from "@/lib/api"
import { NotificationPanel } from "./notification-panel"
import { ThemeToggle } from "./theme-toggle"
import { UserMenu } from "./user-menu"

interface DashboardHeaderProps {
  onStockSelect?: (symbol: string) => void
}

/**
 * Full-width bar above the sidebar: 64px, one hairline underneath. The mark and
 * wordmark lead, search sits immediately beside them rather than floating in
 * the middle, and the account block anchors the right edge.
 *
 * It sits on --nav rather than --card so the two themes can disagree: white on
 * light, true black on dark — the one surface in the app that goes to pure
 * black, which is what separates the bar from the tiles beneath it.
 */
export function DashboardHeader({ onStockSelect }: DashboardHeaderProps) {
  const handleStockSelect = (stock: StockSymbol) => {
    if (onStockSelect) {
      onStockSelect(stock.symbol)
    }
  }

  return (
    <header className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-5 border-b border-border bg-nav px-5 text-nav-foreground">
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
        <Button variant="ghost" size="icon" className="hidden size-9 rounded-full md:inline-flex">
          <Share2 className="size-[17px]" />
          <span className="sr-only">Chia sẻ</span>
        </Button>

        <div className="hidden sm:block">
          <ThemeToggle />
        </div>

        <div className="hidden items-center gap-1.5 sm:flex">
          {/* Notifications - Job Status Panel */}
          <NotificationPanel />
          <UserMenu />
        </div>
        <Button variant="ghost" size="icon" className="size-9 rounded-full sm:hidden">
          <MoreHorizontal className="size-[17px]" />
          <span className="sr-only">Mở menu</span>
        </Button>
      </div>
    </header>
  )
}
