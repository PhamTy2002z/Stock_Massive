/**
 * PROTOTYPE — throwaway route for issue #21. Not a product surface; delete with
 * the branch once a variant wins.
 *
 * Four variants of the nightly Analysis artifact on one route, switchable via
 * `?variant=A|B|C|D`, with `?symbol=VCB|VHM|MWG` swapping the industry fixture.
 *
 * Hosted inside the real DashboardLayout with `bleed` so it is judged against
 * the real sidebar, header and density rather than in a vacuum — Alpha Desk has
 * no page yet, so there is nothing else to embed it in.
 */

import { Suspense } from "react"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import { AnalysisArtifactPrototype } from "./_components/client"

interface PageProps {
  searchParams: Promise<{ variant?: string; symbol?: string }>
}

export default async function AnalysisArtifactPrototypePage({ searchParams }: PageProps) {
  const params = await searchParams

  return (
    <DashboardLayoutClient bleed>
      <Suspense fallback={null}>
        <AnalysisArtifactPrototype
          variant={params.variant ?? "A"}
          symbol={params.symbol ?? "VCB"}
        />
      </Suspense>
    </DashboardLayoutClient>
  )
}
