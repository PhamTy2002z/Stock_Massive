"use client"

import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"
import { AppSidebar } from "./app-sidebar"
import { DashboardHeader } from "./dashboard-header"
import { JobProgressBar } from "./job-progress-bar"

interface DashboardLayoutProps {
  children: React.ReactNode
  onStockSelect?: (symbol: string) => void
  /**
   * Hands the full content box to the page, with no padding and no scrolling
   * of its own. A page needs this when something inside it has to touch the
   * chrome — a settings rail that sits flush against the sidebar and runs the
   * full height — which it cannot do from inside a padded, scrolling main.
   * Such a page owns its own scroll containers.
   */
  bleed?: boolean
}

// Matches the header's h-16. The sidebar starts below the bar rather than
// beside it, so it needs to know how much of the viewport is already spoken for.
const HEADER_HEIGHT = "4rem"

export function DashboardLayout({ children, onStockSelect, bleed }: DashboardLayoutProps) {
  return (
    /* A bleeding page is pinned to exactly one viewport rather than allowed to
       grow: the page itself must not scroll, or the whole frame — rail and all
       — travels with the content instead of the content moving inside it. */
    <div
      className={cn(
        "flex w-full flex-col",
        bleed ? "h-svh overflow-hidden" : "min-h-svh"
      )}
    >
      <DashboardHeader onStockSelect={onStockSelect} />
      {/* Rail is the only desktop mode: there is no pin control, so the sidebar
          must not start pinned open. */}
      <SidebarProvider
        defaultOpen={false}
        className="min-h-0 flex-1"
        style={{ "--sidebar-top": HEADER_HEIGHT } as React.CSSProperties}
      >
        <AppSidebar />
        {/* SidebarInset carries its own min-height of one viewport less the
            header. Under bleed that floor is what pushes the frame past the
            screen, so it is released and the flex row sizes it instead. */}
        <SidebarInset className={cn(bleed && "min-h-0")}>
          <JobProgressBar />
          <main
            className={cn(
              "min-h-0 flex-1",
              bleed ? "overflow-hidden" : "overflow-auto p-6"
            )}
          >
            {children}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </div>
  )
}
