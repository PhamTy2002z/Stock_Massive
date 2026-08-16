"use client"

import { useRouter } from "next/navigation"
import { ChevronDown, HelpCircle, LogIn, LogOut, Settings, User } from "lucide-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "@/hooks/use-auth"

/**
 * The account row at the foot of the sidebar.
 *
 * The reference closes its panel on a full-width row rather than on a pill in
 * a top bar: a 26px avatar, the name with the workspace after it in quiet ink,
 * and a chevron on the right. The menu opens *upwards* from it, which is why
 * the identity line moved into the menu — a row this compact cannot carry the
 * email as well, and the menu has room to state it before anything else.
 *
 * The avatar is the one gradient in the system. It is an identity token, not a
 * control, so it is allowed the teal without spending the "one filled control
 * per view" budget.
 */
export function UserMenu() {
  const router = useRouter()
  const { user, signOut } = useAuth()

  // No avatar_url now that accounts are local rather than OAuth profiles —
  // AvatarFallback carries the initials instead.
  const userName = user?.full_name || user?.email?.split("@")[0] || "User"
  const userEmail = user?.email || ""
  const userAvatar = ""
  const userInitials = userName.slice(0, 2).toUpperCase()

  if (!user) {
    return (
      <Button
        variant="ghost"
        className="h-10 w-full justify-start gap-2.5 px-2"
        onClick={() => router.push("/login")}
      >
        <LogIn className="size-4" />
        <span className="truncate group-data-[collapsible=icon]:hidden">Đăng nhập</span>
      </Button>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Account menu for ${userName}`}
          className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left outline-none ring-sidebar-ring transition-colors hover:bg-foreground/[0.035] focus-visible:ring-2 data-[state=open]:bg-foreground/[0.05] group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
        >
          <Avatar className="size-[26px] shrink-0 rounded-full">
            <AvatarImage src={userAvatar} alt={userName} />
            <AvatarFallback className="rounded-full bg-[linear-gradient(120deg,#e8c454,#78d0cd)] text-[0.76rem] font-semibold text-[#0c0c0c]">
              {userInitials}
            </AvatarFallback>
          </Avatar>
          <span className="min-w-0 flex-1 truncate text-control group-data-[collapsible=icon]:hidden">
            {userName}
          </span>
          <ChevronDown className="size-[15px] shrink-0 text-muted-foreground group-data-[collapsible=icon]:hidden" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="min-w-[15rem]"
        side="top"
        align="start"
        sideOffset={8}
      >
        <DropdownMenuLabel className="px-2.5 py-1.5 text-control font-normal text-muted-foreground">
          {userEmail}
        </DropdownMenuLabel>
        <DropdownMenuGroup>
          <DropdownMenuItem>
            <User className="mr-1 size-4" />
            Hồ sơ
          </DropdownMenuItem>
          {/* Profile and Help are still inert; Settings is the one that leads
              somewhere now that /settings exists. */}
          <DropdownMenuItem
            className="cursor-pointer"
            onClick={() => router.push("/settings")}
          >
            <Settings className="mr-1 size-4" />
            Cài đặt
          </DropdownMenuItem>
          <DropdownMenuItem>
            <HelpCircle className="mr-1 size-4" />
            Trợ giúp
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="cursor-pointer text-destructive hover:text-destructive focus:text-destructive"
          onClick={() => signOut()}
        >
          <LogOut className="mr-1 size-4" />
          Đăng xuất
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
