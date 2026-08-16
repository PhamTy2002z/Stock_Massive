import { Suspense } from "react"
import type { Metadata } from "next"

import { AlphaDesk } from "@/components/alpha/desk"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"

// The surface reads the signed-in user's Watchlist and Threads, so there is
// nothing to prerender: a build-time snapshot would ship somebody else's.
export const dynamic = "force-dynamic"

export const metadata: Metadata = {
  title: "Alpha Desk · VisgniteAI",
}

export default function AlphaDeskPage() {
  return (
    /* bleed: the conversation runs the full height and owns its own scroll
       container, which it cannot do from inside a padded, scrolling main. */
    <DashboardLayoutClient bleed>
      {/* `useSearchParams` reads the `?symbol=` deep link, and Next requires a
          boundary around any component that does. */}
      <Suspense>
        <AlphaDesk />
      </Suspense>
    </DashboardLayoutClient>
  )
}
