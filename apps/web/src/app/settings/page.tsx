import type { Metadata } from "next"

import { SettingsView } from "./_components/settings-view"

// The page reads the signed-in account, so it is rendered per request.
export const dynamic = "force-dynamic"

export const metadata: Metadata = {
  title: "Cài đặt · VisgniteAI",
}

export default function SettingsPage() {
  return <SettingsView />
}
