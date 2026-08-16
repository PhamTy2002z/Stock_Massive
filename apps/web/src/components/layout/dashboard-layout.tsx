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

/**
 * The frame: a full-height sidebar on the left, everything else beside it.
 *
 * The bar used to run the full width *above* the sidebar, which made the brand
 * a property of the window rather than of the panel. The reference does the
 * opposite — the sidebar owns the mark and the account and runs floor to
 * ceiling, and the bar above the content belongs to the page it sits on. So
 * the header moved inside the inset, and `--sidebar-top` went back to zero.
 */
export function DashboardLayout({ children, onStockSelect, bleed }: DashboardLayoutProps) {
  return (
    /* A bleeding page is pinned to exactly one viewport rather than allowed to
       grow: the page itself must not scroll, or the whole frame — rail and all
       — travels with the content instead of the content moving inside it. */
    <SidebarProvider
      defaultOpen
      className={cn("w-full", bleed ? "h-svh overflow-hidden" : "min-h-svh")}
    >
      <AppSidebar />
      {/* SidebarInset carries its own min-height of one viewport. Under bleed
          that floor is what pushes the frame past the screen, so it is released
          and the flex row sizes it instead. */}
      <SidebarInset className={cn("min-w-0", bleed && "min-h-0")}>
        <DashboardHeader onStockSelect={onStockSelect} />
        <JobProgressBar />
        <main
          className={cn(
            "min-h-0 flex-1",
            bleed ? "overflow-hidden" : "overflow-auto p-5"
          )}
        >
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
