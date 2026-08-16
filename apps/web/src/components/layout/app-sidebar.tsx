"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import Link from "next/link"
import {
  Activity,
  Gauge,
  ListChecks,
  Map,
  MessagesSquare,
} from "lucide-react"

import { VisgniteWordmark } from "@/components/shared/visgnite-logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { UserMenu } from "./user-menu"

type NavItem = {
  title: string
  url: string
  icon: React.ComponentType<{ className?: string }>
}

// Flat destinations only. Hover-expand and nested accordions are incompatible:
// the user opens a group, moves to read it, drifts 2px off the overlay and loses
// everything. Grouping is expressed with separators, nothing unfolds.
const navGroups: NavItem[][] = [
  // Alpha Desk first: the existing tabs are for looking up numbers, and this
  // is the one for asking what to do about them (`docs/specs/0002` §1).
  [{ title: "Alpha Desk", url: "/alpha-desk", icon: MessagesSquare }],
  [{ title: "Market Map", url: "/", icon: Map }],
  [
    { title: "Stock 360", url: "/analytics/deep-dive", icon: Gauge },
    { title: "Trends & Signals", url: "/analytics/volume-spikes", icon: Activity },
  ],
  // The Watchlist is the one destination that is about the signed-in user
  // rather than about the market, which is why it sits in its own group.
  [{ title: "Watchlist", url: "/watchlist", icon: ListChecks }],
]

function NavMain() {
  const pathname = usePathname()

  const isPathActive = (url: string) =>
    url === "/" ? pathname === "/" : pathname.startsWith(url)

  return (
    <>
      {navGroups.map((group, groupIndex) => (
        <React.Fragment key={group[0].title}>
          {groupIndex > 0 && <SidebarSeparator className="my-0" />}
          <SidebarGroup className="py-1">
            <SidebarMenu>
              {group.map((item) => {
                const isActive = isPathActive(item.url)
                return (
                  <SidebarMenuItem key={item.title}>
                    {/* Active styling comes from the button's own
                        data-[active=true] variant. The orange bg-primary
                        override that used to be here never won the cascade
                        against it, so it only made the intent unreadable. */}
                    <SidebarMenuButton
                      tooltip={item.title}
                      isActive={isActive}
                      asChild
                    >
                      <Link href={item.url} aria-label={item.title}>
                        <item.icon />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroup>
        </React.Fragment>
      ))}
    </>
  )
}

/**
 * The left rail, and the panel that carries the brand.
 *
 * The reference puts the mark at the top of the sidebar rather than in a bar
 * above it — the panel runs the full height of the viewport, opens onto
 * navigation and closes on the account row. That is why the header and the
 * footer live here now instead of in the top bar: the bar above the content is
 * about *the page you are on*, and this panel is about the product.
 *
 * Collapsed to the icon rail the wordmark drops to the mark alone, so nothing
 * in the panel changes height as it opens.
 */
export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="flex-row items-center gap-1.5 group-data-[collapsible=icon]:justify-center">
        <Link
          href="/"
          aria-label="VisgniteAI"
          className="flex min-w-0 items-center rounded-lg px-1 py-0.5 text-foreground outline-none transition-opacity hover:opacity-80 focus-visible:ring-2 focus-visible:ring-sidebar-ring group-data-[collapsible=icon]:px-0"
        >
          {/* On the rail the wordmark is the mark alone — the text node is the
              element's own last child, which is what the selector drops. */}
          <VisgniteWordmark className="group-data-[collapsible=icon]:gap-0 group-data-[collapsible=icon]:text-[0px]" />
        </Link>
        {/* The collapse control sits with the mark, the way the reference draws
            it. Hidden on the rail: there is no room for it beside the mark, and
            the rail opens on approach anyway. */}
        <SidebarTrigger className="ml-auto size-[30px] rounded-lg group-data-[collapsible=icon]:hidden" />
      </SidebarHeader>

      <SidebarContent className="pt-1">
        <NavMain />
      </SidebarContent>

      <SidebarFooter className="p-2">
        <UserMenu />
      </SidebarFooter>
    </Sidebar>
  )
}
