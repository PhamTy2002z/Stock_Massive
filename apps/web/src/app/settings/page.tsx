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
    /* bleed: the rail has to sit flush against the app sidebar and run the
       full height, which it cannot do from inside a padded, scrolling main. */
    <DashboardLayoutClient bleed>
      <SettingsView />
    </DashboardLayoutClient>
  )
}
