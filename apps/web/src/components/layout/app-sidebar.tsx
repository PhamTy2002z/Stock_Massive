"use client"

import * as React from "react"
import {
  BarChart3,
  Bookmark,
  ChevronRight,
  LayoutDashboard,
  LineChart,
  PieChart,
  Star,
  Table2,
  TrendingUp,
  Wallet,
} from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
} from "@/components/ui/sidebar"

const data = {
  navMain: [
    {
      title: "Dashboard",
      url: "/",
      icon: LayoutDashboard,
      isActive: true,
    },
    {
      title: "Analytics",
      url: "#",
      icon: BarChart3,
      items: [
        { title: "Reports", url: "#" },
        { title: "Insights", url: "#" },
        { title: "Alerts", url: "#" },
      ],
    },
    {
      title: "Markets",
      url: "#",
      icon: TrendingUp,
      items: [
        { title: "Overview", url: "#" },
        { title: "Stocks", url: "#" },
        { title: "Indices", url: "#" },
        { title: "Sectors", url: "#" },
      ],
    },
    {
      title: "Charts",
      url: "#",
      icon: LineChart,
      items: [
        { title: "TradingView", url: "#" },
        { title: "Technical Analysis", url: "#" },
        { title: "Comparisons", url: "#" },
      ],
    },
    {
      title: "Screener",
      url: "#",
      icon: Table2,
      items: [
        { title: "Stock Screener", url: "#" },
        { title: "Saved Screens", url: "#" },
        { title: "Top Gainers", url: "#" },
        { title: "Top Losers", url: "#" },
      ],
    },
    {
      title: "Portfolio",
      url: "#",
      icon: PieChart,
      items: [
        { title: "Holdings", url: "#" },
        { title: "Performance", url: "#" },
        { title: "Transactions", url: "#" },
      ],
    },
  ],
  watchlists: [
    { name: "Tech Giants", url: "#", icon: Star },
    { name: "Dividend Stocks", url: "#", icon: Wallet },
    { name: "Growth Picks", url: "#", icon: TrendingUp },
  ],
}

function SidebarBrand() {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton size="lg" className="cursor-default hover:bg-transparent">
          <img
            src="/logo.png"
            alt="Stock Massive"
            className="size-10 object-contain"
          />
          <div className="grid flex-1 text-left text-sm leading-tight">
            <span className="truncate font-bold text-base">Stock Massive</span>
            <span className="truncate text-xs text-muted-foreground">Analytics Platform</span>
          </div>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

function NavMain({
  items,
}: {
  items: typeof data.navMain
}) {
  return (
    <SidebarGroup>
      <SidebarGroupLabel>Navigation</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => {
          const hasSubItems = item.items && item.items.length > 0

          if (!hasSubItems) {
            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton tooltip={item.title} isActive={item.isActive} asChild>
                  <a href={item.url}>
                    {item.icon && <item.icon />}
                    <span>{item.title}</span>
                  </a>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          }

          return (
            <Collapsible
              key={item.title}
              asChild
              defaultOpen={item.isActive}
              className="group/collapsible"
            >
              <SidebarMenuItem>
                <CollapsibleTrigger asChild>
                  <SidebarMenuButton tooltip={item.title}>
                    {item.icon && <item.icon />}
                    <span>{item.title}</span>
                    <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                  </SidebarMenuButton>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <SidebarMenuSub>
                    {item.items?.map((subItem) => (
                      <SidebarMenuSubItem key={subItem.title}>
                        <SidebarMenuSubButton asChild>
                          <a href={subItem.url}>
                            <span>{subItem.title}</span>
                          </a>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    ))}
                  </SidebarMenuSub>
                </CollapsibleContent>
              </SidebarMenuItem>
            </Collapsible>
          )
        })}
      </SidebarMenu>
    </SidebarGroup>
  )
}

function NavWatchlists({
  watchlists,
}: {
  watchlists: typeof data.watchlists
}) {
  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>Watchlists</SidebarGroupLabel>
      <SidebarMenu>
        {watchlists.map((item) => (
          <SidebarMenuItem key={item.name}>
            <SidebarMenuButton asChild>
              <a href={item.url}>
                <item.icon className="text-muted-foreground" />
                <span>{item.name}</span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ))}
        <SidebarMenuItem>
          <SidebarMenuButton className="text-sidebar-foreground/70">
            <Bookmark className="text-sidebar-foreground/70" />
            <span>Create Watchlist</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  )
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarBrand />
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} />
        <NavWatchlists watchlists={data.watchlists} />
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
