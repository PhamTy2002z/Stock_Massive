"use client"

import { useRouter } from "next/navigation"
import { ChevronsUpDown, HelpCircle, LogIn, LogOut, Settings, User } from "lucide-react"

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
 * Account block for the top bar. Below md the name and email drop away and the
 * avatar alone carries it — two lines of text plus the search field do not fit
 * a 3.5rem bar on a phone.
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
        className="h-9 gap-2 px-2"
        onClick={() => router.push("/login")}
      >
        <LogIn className="size-4" />
        <span className="hidden text-sm font-medium md:inline">Sign in</span>
      </Button>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Account menu for ${userName}`}
          className="flex items-center gap-2.5 rounded-full border border-[hsl(var(--hairline))] bg-muted/60 py-1 pl-1 pr-3 outline-none ring-sidebar-ring transition-colors hover:bg-sidebar-accent focus-visible:ring-2 data-[state=open]:bg-sidebar-accent"
        >
          <Avatar className="size-8 shrink-0 rounded-full">
            <AvatarImage src={userAvatar} alt={userName} />
            <AvatarFallback className="rounded-full bg-foreground text-background text-[13px] font-semibold tracking-[-0.208px]">
              {userInitials}
            </AvatarFallback>
          </Avatar>
          <div className="hidden min-w-0 max-w-44 grid-flow-row text-left md:grid">
            <span className="truncate text-[13px] font-semibold leading-[1.29] tracking-[-0.208px]">
              {userName}
            </span>
            <span className="truncate text-[11px] leading-[1.3] tracking-[-0.11px] text-muted-foreground">
              {userEmail}
            </span>
          </div>
          <ChevronsUpDown className="hidden size-[13px] shrink-0 text-muted-foreground md:block" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-56 rounded-lg" side="bottom" align="end" sideOffset={6}>
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
            Help &amp; Support
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive hover:text-destructive focus:text-destructive cursor-pointer"
          onClick={() => signOut()}
        >
          <LogOut className="mr-2 size-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
