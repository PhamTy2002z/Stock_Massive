"use client"

import * as React from "react"
import { useId, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import Link from "next/link"
import {
  BarChart3,
  Bookmark,
  ChevronRight,
  ChevronsUpDown,
  HelpCircle,
  LayoutDashboard,
  LineChart,
  LogIn,
  LogOut,
  PanelLeft,
  PieChart,
  Settings,
  Star,
  Table2,
  TrendingUp,
  User,
  Wallet,
} from "lucide-react"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
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
  useSidebar,
} from "@/components/ui/sidebar"
import { useAuth } from "@/hooks/use-auth"

const data = {
  navMain: [
    {
      title: "Overview",
      url: "/",
      icon: LayoutDashboard,
    },
    {
      title: "Analytics",
      url: "#",
      icon: BarChart3,
      items: [
        { title: "Deep Dive", url: "/analytics/deep-dive" },
        { title: "Financial Statements", url: "/analytics/financial-statements" },
        { title: "Volume Spikes", url: "/analytics/volume-spikes" },
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
  const { state, toggleSidebar } = useSidebar()
  const isCollapsed = state === "collapsed"
  const [isHovered, setIsHovered] = useState(false)

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton
          size="lg"
          className={
            isCollapsed
              ? "cursor-pointer"
              : "cursor-default hover:bg-transparent"
          }
          onClick={isCollapsed ? toggleSidebar : undefined}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          {/* Icon container - keeps consistent sizing for centering */}
          <div className="relative size-8 flex items-center justify-center shrink-0">
            {/* Logo - visible when expanded OR when collapsed and not hovered */}
            <img
              src="/logo.png"
              alt="Stock Massive"
              className={`size-10 object-contain absolute transition-all duration-200 ${
                isCollapsed && isHovered ? "opacity-0 scale-75" : "opacity-100 scale-100"
              }`}
            />
            {/* Panel icon - visible only when collapsed and hovered */}
            <PanelLeft
              className={`size-5 absolute transition-all duration-200 ${
                isCollapsed && isHovered ? "opacity-100 scale-100" : "opacity-0 scale-75"
              }`}
            />
          </div>
          <div className="grid flex-1 text-left text-sm leading-tight transition-[opacity,transform] duration-200 ease-sidebar group-data-[collapsible=icon]:opacity-0 group-data-[collapsible=icon]:scale-95">
            <span className="truncate font-bold text-base">Stock Massive</span>
            <span className="truncate text-xs text-muted-foreground">Analytics Platform</span>
          </div>
          {/* Toggle button - visible only when expanded */}
          {!isCollapsed && (
            <div
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation()
                toggleSidebar()
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.stopPropagation()
                  toggleSidebar()
                }
              }}
              className="ml-auto p-1.5 rounded-md hover:bg-sidebar-accent transition-colors cursor-pointer"
              aria-label="Close sidebar"
            >
              <PanelLeft className="size-4" />
            </div>
          )}
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

// Separate component for collapsible nav items to ensure stable IDs
function CollapsibleNavItem({
  item,
  isPathActive,
}: {
  item: (typeof data.navMain)[0]
  isPathActive: (url: string) => boolean
}) {
  const collapsibleId = useId()
  const hasActiveSubItem = item.items?.some((sub) => isPathActive(sub.url)) ?? false

  return (
    <Collapsible
      asChild
      defaultOpen={hasActiveSubItem}
      className="group/collapsible"
    >
      <SidebarMenuItem>
        <CollapsibleTrigger asChild id={`trigger-${collapsibleId}`}>
          <SidebarMenuButton tooltip={item.title}>
            {item.icon && <item.icon />}
            <span>{item.title}</span>
            <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
          </SidebarMenuButton>
        </CollapsibleTrigger>
        <CollapsibleContent id={`content-${collapsibleId}`}>
          <SidebarMenuSub>
            {item.items?.map((subItem) => {
              const subIsActive = isPathActive(subItem.url)
              return (
                <SidebarMenuSubItem key={subItem.title}>
                  <SidebarMenuSubButton
                    isActive={subIsActive}
                    className={subIsActive ? "bg-primary text-primary-foreground font-medium hover:bg-primary/90 hover:text-primary-foreground" : ""}
                    asChild
                  >
                    <Link href={subItem.url}>
                      <span>{subItem.title}</span>
                    </Link>
                  </SidebarMenuSubButton>
                </SidebarMenuSubItem>
              )
            })}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  )
}

function NavMain({
  items,
}: {
  items: typeof data.navMain
}) {
  const pathname = usePathname()

  // Check if a path is active (exact match or starts with for sub-routes)
  const isPathActive = (url: string) => {
    if (url === "#") return false
    if (url === "/") return pathname === "/"
    return pathname.startsWith(url)
  }

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Navigation</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => {
          const hasSubItems = item.items && item.items.length > 0
          const isActive = isPathActive(item.url)

          if (!hasSubItems) {
            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  tooltip={item.title}
                  isActive={isActive}
                  className={isActive ? "bg-primary text-primary-foreground font-medium hover:bg-primary/90 hover:text-primary-foreground" : ""}
                  asChild
                >
                  <Link href={item.url}>
                    {item.icon && <item.icon />}
                    <span>{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          }

          return (
            <CollapsibleNavItem
              key={item.title}
              item={item}
              isPathActive={isPathActive}
            />
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
    <SidebarGroup className="transition-[opacity,transform] duration-200 ease-sidebar group-data-[collapsible=icon]:opacity-0 group-data-[collapsible=icon]:scale-95 group-data-[collapsible=icon]:pointer-events-none">
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

function SidebarUserSection() {
  const router = useRouter()
  const { isMobile } = useSidebar()
  const { user, signOut } = useAuth()

  const handleSignOut = () => signOut()

  // No avatar_url now that accounts are local rather than OAuth profiles —
  // AvatarFallback carries the initials instead.
  const userName = user?.full_name || user?.email?.split("@")[0] || "User"
  const userEmail = user?.email || ""
  const userAvatar = ""
  const userInitials = userName.slice(0, 2).toUpperCase()

  if (!user) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            size="lg"
            tooltip="Sign in"
            onClick={() => router.push("/login")}
            className="cursor-pointer group-data-[collapsible=icon]:!w-8 group-data-[collapsible=icon]:!h-8 group-data-[collapsible=icon]:!p-0 group-data-[collapsible=icon]:!gap-0 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:mx-auto group-data-[collapsible=icon]:mb-2"
          >
            <div className="flex size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground shrink-0 group-data-[collapsible=icon]:mx-auto">
              <LogIn className="size-4" />
            </div>
            <div className="grid flex-1 text-left text-sm leading-tight transition-[opacity,width] duration-200 ease-sidebar group-data-[collapsible=icon]:opacity-0 group-data-[collapsible=icon]:w-0 group-data-[collapsible=icon]:overflow-hidden">
              <span className="truncate font-semibold">Sign in</span>
              <span className="truncate text-xs text-muted-foreground">Access your account</span>
            </div>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    )
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              tooltip={userName}
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground group-data-[collapsible=icon]:!w-8 group-data-[collapsible=icon]:!h-8 group-data-[collapsible=icon]:!p-0 group-data-[collapsible=icon]:!gap-0 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:mx-auto group-data-[collapsible=icon]:mb-2"
            >
              <Avatar className="size-8 rounded-lg shrink-0 transition-transform duration-200 group-data-[collapsible=icon]:mx-auto">
                <AvatarImage src={userAvatar} alt={userName} />
                <AvatarFallback className="rounded-lg bg-primary text-primary-foreground font-medium text-sm">
                  {userInitials}
                </AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight transition-[opacity,width] duration-200 ease-sidebar group-data-[collapsible=icon]:opacity-0 group-data-[collapsible=icon]:w-0 group-data-[collapsible=icon]:overflow-hidden">
                <span className="truncate font-semibold">{userName}</span>
                <span className="truncate text-xs text-muted-foreground">{userEmail}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4 shrink-0 transition-[opacity,width] duration-200 ease-sidebar group-data-[collapsible=icon]:opacity-0 group-data-[collapsible=icon]:w-0" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <Avatar className="size-8 rounded-lg">
                  <AvatarImage src={userAvatar} alt={userName} />
                  <AvatarFallback className="rounded-lg bg-primary text-primary-foreground font-medium text-sm">
                    {userInitials}
                  </AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">{userName}</span>
                  <span className="truncate text-xs text-muted-foreground">{userEmail}</span>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem>
                <User className="mr-2 size-4" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Settings className="mr-2 size-4" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuItem>
                <HelpCircle className="mr-2 size-4" />
                Help & Support
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive hover:text-destructive focus:text-destructive cursor-pointer"
              onClick={handleSignOut}
            >
              <LogOut className="mr-2 size-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
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
      <SidebarFooter>
        <SidebarUserSection />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
