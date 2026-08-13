import { Suspense } from "react"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import {
  VolumeSpikeDashboard,
  VolumeSpikeDashboardSkeleton,
} from "@/components/dashboard"

// The signal is read from the store on every request, so there is nothing here
// to prerender: a build-time snapshot would ship whichever session happened to
// be newest when the image was built, and the build would fail whenever no API
// is reachable from the build host.
export const dynamic = "force-dynamic"

export default function VolumeSpikesPage() {
  return (
    <Suspense
      fallback={
        <DashboardLayoutClient>
          <VolumeSpikeDashboardSkeleton />
        </DashboardLayoutClient>
      }
    >
      <DashboardLayoutClient>
        <VolumeSpikeDashboard />
      </DashboardLayoutClient>
    </Suspense>
  )
}
