"use client"

import * as React from "react"
import { usePathname, useRouter } from "next/navigation"
import Link from "next/link"
import {
  Activity,
  ChevronsUpDown,
  FileText,
  Gauge,
  GitCompare,
  HelpCircle,
  LayoutGrid,
  LogIn,
  LogOut,
  Map,
  Pin,
  PinOff,
  Settings,
  User,
} from "lucide-react"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
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
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar"
import { useAuth } from "@/hooks/use-auth"

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
    { title: "Financials", url: "/analytics/financial-statements", icon: FileText },
    { title: "Compare", url: "/compare", icon: GitCompare },
    { title: "Trends & Signals", url: "/analytics/volume-spikes", icon: Activity },
  ],
  [{ title: "Workspaces", url: "/workspaces", icon: LayoutGrid }],
]

function SidebarBrand() {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton size="lg" tooltip="Stock Massive" asChild>
          <Link href="/">
            <div className="relative size-8 flex items-center justify-center shrink-0">
              <img
                src="/logo.png"
                alt="Stock Massive"
                className="size-10 object-contain"
              />
            </div>
            <div className="grid flex-1 text-left text-sm leading-tight transition-[opacity,transform] duration-200 ease-sidebar group-data-[collapsible=icon]:opacity-0 group-data-[collapsible=icon]:scale-95">
              <span className="truncate font-bold text-base">Stock Massive</span>
              <span className="truncate text-xs text-muted-foreground">
                Analytics Platform
              </span>
            </div>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

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
                    <SidebarMenuButton
                      tooltip={item.title}
                      isActive={isActive}
                      className={
                        isActive
                          ? "bg-primary text-primary-foreground font-medium hover:bg-primary/90 hover:text-primary-foreground"
                          : ""
                      }
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

function SidebarPinToggle() {
  const { mode, toggleSidebar, isMobile } = useSidebar()

  if (isMobile) return null

  const isPinned = mode === "pinned"

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton
          tooltip={isPinned ? "Bỏ ghim menu (⌘B)" : "Ghim menu mở (⌘B)"}
          onClick={toggleSidebar}
          aria-pressed={isPinned}
          aria-label={isPinned ? "Bỏ ghim menu" : "Ghim menu mở"}
          className="text-sidebar-foreground/70"
        >
          {isPinned ? <PinOff /> : <Pin />}
          <span>{isPinned ? "Bỏ ghim menu" : "Ghim menu"}</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
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
        <NavMain />
      </SidebarContent>
      <SidebarFooter>
        <SidebarPinToggle />
        <SidebarUserSection />
      </SidebarFooter>
    </Sidebar>
  )
}
