import type { Metadata } from "next"

import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import { SettingsView } from "./_components/settings-view"

// The dashboard chrome reads the signed-in user, so this page is per-request.
export const dynamic = "force-dynamic"

export const metadata: Metadata = {
  title: "Cài đặt · Stock Massive",
}

export default function SettingsPage() {
  return (
    <DashboardLayoutClient>
      <SettingsView />
    </DashboardLayoutClient>
  )
}
