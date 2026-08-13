"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import Link from "next/link"
import {
  Activity,
  Gauge,
  Map,
} from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar"

type NavItem = {
  title: string
  url: string
  icon: React.ComponentType<{ className?: string }>
}

// Flat destinations only. Hover-expand and nested accordions are incompatible:
// the user opens a group, moves to read it, drifts 2px off the overlay and loses
// everything. Grouping is expressed with separators, nothing unfolds.
const navGroups: NavItem[][] = [
  [{ title: "Market Map", url: "/", icon: Map }],
  [
    { title: "Stock 360", url: "/analytics/deep-dive", icon: Gauge },
    { title: "Trends & Signals", url: "/analytics/volume-spikes", icon: Activity },
  ],
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

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  // No SidebarHeader: the logo lives in the full-width bar above, so the rail
  // opens straight onto navigation.
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarContent className="pt-2">
        <NavMain />
      </SidebarContent>
    </Sidebar>
  )
}
