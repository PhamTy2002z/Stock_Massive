"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import { Search, Share2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar"
import { StockSearchBar } from "@/components/dashboard"
import { StockSymbol } from "@/lib/api"
import { getMarketSession } from "@/lib/market-session"
import { cn } from "@/lib/utils"
import { NotificationPanel } from "./notification-panel"
import { ThemeToggle } from "./theme-toggle"

interface DashboardHeaderProps {
  onStockSelect?: (symbol: string) => void
}

// What the bar says you are looking at. Longest prefix wins, so
// /analytics/deep-dive does not answer to the "/" entry.
const PAGE_TITLES: [prefix: string, title: string][] = [
  ["/alpha-desk", "Alpha Desk"],
  ["/analytics/deep-dive", "Stock 360"],
  ["/analytics/volume-spikes", "Trends & Signals"],
  ["/watchlist", "Danh mục theo dõi"],
  ["/portfolio", "Danh mục đầu tư"],
  ["/charts", "Biểu đồ"],
  ["/settings", "Cài đặt"],
  ["/", "Bản đồ thị trường"],
]

function pageTitle(pathname: string): string {
  const match = PAGE_TITLES.filter(([prefix]) =>
    prefix === "/" ? pathname === "/" : pathname.startsWith(prefix)
  ).sort((a, b) => b[0].length - a[0].length)[0]
  return match?.[1] ?? "VisgniteAI"
}

/**
 * The session stamp: a dot, the exchange, and what the clock is doing.
 *
 * Rendered only after mount. The phase is read from the viewer's clock, so a
 * server render would state whichever phase the *server* was in and the first
 * client frame would disagree with it — a hydration mismatch over a label
 * nobody is waiting on.
 */
function MarketStamp() {
  const [session, setSession] = React.useState<ReturnType<typeof getMarketSession> | null>(
    null
  )

  React.useEffect(() => {
    const tick = () => setSession(getMarketSession())
    tick()
    // A minute is finer than any boundary in the schedule.
    const timer = setInterval(tick, 60_000)
    return () => clearInterval(timer)
  }, [])

  if (!session) return null

  return (
    <span className="hidden items-center gap-1.5 whitespace-nowrap font-mono text-micro text-muted-foreground xl:flex">
      <i
        aria-hidden="true"
        className={cn(
          "block size-[5px] rounded-full",
          session.isLive ? "bg-positive" : "bg-ink-6"
        )}
      />
      HOSE · {session.label}
    </span>
  )
}

/**
 * The bar above the content — 52px, one hairline underneath, and no brand on
 * it. The mark and the account both live in the sidebar now, which leaves this
 * row to say what the reference's header says: where you are, what you can
 * search, whether the market is open, and the two or three actions that apply
 * to the page under it.
 *
 * It sits on --nav rather than --card so the two themes can disagree about it.
 */
export function DashboardHeader({ onStockSelect }: DashboardHeaderProps) {
  const pathname = usePathname()
  const { state, isMobile } = useSidebar()

  const handleStockSelect = (stock: StockSymbol) => {
    if (onStockSelect) {
      onStockSelect(stock.symbol)
    }
  }

  return (
    <header className="sticky top-0 z-30 flex h-[52px] shrink-0 items-center gap-3 border-b border-border bg-nav px-4 text-nav-foreground">
      {/* Only when the panel is shut. Open, the control lives with the mark in
          the sidebar head and a second copy here would be two ways to do one
          thing, six pixels apart. */}
      {(state === "collapsed" || isMobile) && (
        <SidebarTrigger className="size-[30px] shrink-0 animate-vg-fade-in rounded-lg" />
      )}

      <h1 className="min-w-0 shrink-0 truncate text-[0.95rem] font-medium tracking-[-0.012em] text-ink-2">
        {pageTitle(pathname)}
      </h1>

      {/* Grows with the header up to the design's 420px ceiling. */}
      <div className="hidden max-w-[420px] flex-1 md:block">
        <StockSearchBar
          onSelect={handleStockSelect}
          placeholder="Tìm mã, ngành, chỉ số"
        />
      </div>

      <div className="flex-1" />

      <div className="flex items-center gap-1">
        <MarketStamp />

        {/* Mobile search button */}
        <Button variant="ghost" size="icon-sm" className="md:hidden">
          <Search />
          <span className="sr-only">Tìm kiếm</span>
        </Button>

        <ThemeToggle />

        {/* Notifications - Job Status Panel */}
        <NotificationPanel />

        <Button variant="outline" size="sm" className="hidden gap-1.5 sm:inline-flex">
          <Share2 className="size-[15px]" />
          Chia sẻ
        </Button>
      </div>
    </header>
  )
}
