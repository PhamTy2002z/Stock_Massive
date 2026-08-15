import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import { WatchlistRail } from "@/components/alpha/watchlist-rail"

// One user's Watchlist against whichever session the store last closed. There
// is nothing to prerender: a build-time snapshot would ship somebody else's
// list, and the rail is read per request behind a session cookie.
export const dynamic = "force-dynamic"

export default function WatchlistPage() {
  return (
    <DashboardLayoutClient>
      {/* The rail sizes to its content, so the page decides the box. Bounded
          here rather than stretched: the same component is mounted as a compact
          dock inside Alpha Desk later, and a rail that assumed a full-height
          column would have to be rebuilt there. */}
      <div className="mx-auto w-full max-w-2xl">
        <WatchlistRail />
      </div>
    </DashboardLayoutClient>
  )
}
