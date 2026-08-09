"use client"

import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar"
import { AppSidebar } from "./app-sidebar"
import { DashboardHeader } from "./dashboard-header"
import { JobProgressBar } from "./job-progress-bar"

interface DashboardLayoutProps {
  children: React.ReactNode
  onStockSelect?: (symbol: string) => void
}

// Matches the header's h-16. The sidebar starts below the bar rather than
// beside it, so it needs to know how much of the viewport is already spoken for.
const HEADER_HEIGHT = "4rem"

export function DashboardLayout({ children, onStockSelect }: DashboardLayoutProps) {
  return (
    <div className="flex min-h-svh w-full flex-col">
      <DashboardHeader onStockSelect={onStockSelect} />
      {/* Rail is the only desktop mode: there is no pin control, so the sidebar
          must not start pinned open. */}
      <SidebarProvider
        defaultOpen={false}
        className="min-h-0 flex-1"
        style={{ "--sidebar-top": HEADER_HEIGHT } as React.CSSProperties}
      >
        <AppSidebar />
        <SidebarInset>
          <JobProgressBar />
          <main className="flex-1 overflow-auto p-6">
            {children}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </div>
  )
}
