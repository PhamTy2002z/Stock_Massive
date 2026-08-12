/**
 * PROTOTYPE — throwaway route for issue #22.
 *
 * Three radically different Alpha Desk harness layouts, switchable via
 * `?variant=A|B|C`, and six interaction states via `?state=`. The route uses
 * the real app shell with `bleed`; Alpha Desk has no production route yet.
 */

import { Suspense } from "react"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import { AlphaDeskPrototype } from "./_components/client"

interface PageProps {
  searchParams: Promise<{ variant?: string; state?: string }>
}

export default async function AlphaDeskPrototypePage({ searchParams }: PageProps) {
  const params = await searchParams

  return (
    <DashboardLayoutClient bleed>
      <Suspense fallback={null}>
        <AlphaDeskPrototype
          variant={params.variant ?? "A"}
          state={params.state ?? "ready"}
        />
      </Suspense>
    </DashboardLayoutClient>
  )
}
