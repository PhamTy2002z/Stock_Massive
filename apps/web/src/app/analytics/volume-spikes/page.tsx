import { Suspense } from "react"
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import {
  VolumeSpikeDashboard,
  VolumeSpikeDashboardSkeleton,
} from "@/components/dashboard"

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
