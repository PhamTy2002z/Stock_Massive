"use client"

import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar"
import { AppSidebar } from "./app-sidebar"
import { DashboardHeader } from "./dashboard-header"
import { JobProgressBar } from "./job-progress-bar"

interface DashboardLayoutProps {
  children: React.ReactNode
  onStockSelect?: (symbol: string) => void
}

export function DashboardLayout({ children, onStockSelect }: DashboardLayoutProps) {
  // Rail is the only desktop mode: there is no pin control, so the sidebar must
  // not start pinned open.
  return (
    <SidebarProvider defaultOpen={false}>
      <AppSidebar />
      <SidebarInset>
        <DashboardHeader onStockSelect={onStockSelect} />
        <JobProgressBar />
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
