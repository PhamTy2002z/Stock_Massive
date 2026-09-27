"use client"

import type { ReactNode } from "react"
import {
  Check,
  ChevronDown,
  Download,
  HelpCircle,
  LogOut,
  Settings,
} from "lucide-react"

import { useAuth } from "@/hooks/use-auth"

import { Avatar, Menu, MenuItem, MenuSeparator } from "./primitives"
import { useShell } from "./shell-state"

/**
 * Who is signed in, and the account menu that opens from it.
 *
 * The workspace rows above the separator are the reference's own two — a team
 * and a personal space. There is no workspace resource behind them yet, so they
 * are drawn from the signed-in account and are inert: pressing one changes
 * nothing, and the surface does not pretend a switch happened.
 */
/** `actions` sit on the footer row beside the account, like the sidebar's search. */
export function AccountMenu({ actions }: { actions?: ReactNode }) {
  const { state, dispatch } = useShell()
  const { user, signOut, isSigningOut } = useAuth()
  const open = state.overlay === "account"

  const name = user?.full_name?.trim() || user?.email?.split("@")[0] || "Account"
  const initial = name.charAt(0).toUpperCase()

  return (
    <div className="relative flex-none border-t border-border">
      {open && (
        <Menu className="absolute bottom-[52px] left-2 right-2">
          <p className="px-2.5 pb-1.5 pt-2 text-meta text-ink-6">{user?.email ?? "—"}</p>

          <div className="flex items-center gap-2.5 rounded-[9px] px-2.5 py-2 text-row text-ink-2">
            <Avatar initial={initial} />
            <span className="min-w-0 flex-1 truncate">{name}</span>
            <Check className="size-4 shrink-0 text-primary" strokeWidth={2} />
          </div>

          <MenuSeparator />

          <MenuItem
            icon={<Settings className="size-[17px] text-ink-4" />}
            hint="⇧⌘,"
            onClick={() => dispatch({ type: "overlay", overlay: "settings" })}
          >
            Settings
          </MenuItem>
          {/* No language row. The product commits to one language and carries
              no translation layer, so an entry here — disabled, with a
              chevron promising a submenu — advertised a choice that does not
              exist and will not be built. */}
          <MenuItem icon={<HelpCircle className="size-[17px] text-ink-4" />} disabled>
            Help
          </MenuItem>

          <MenuSeparator />

          {/* No plan row either. Its two halves resolved in opposite directions:
              the allowance is now a real pane inside Settings, two rows above,
              and the plan it would sit beside does not exist until entitlement
              lands. A disabled row reading "allowance" beside a working one is
              worse than no row at all. */}
          <MenuItem icon={<Download className="size-[17px] text-ink-4" />} disabled>
            Download app
          </MenuItem>

          <MenuSeparator />

          <MenuItem
            icon={<LogOut className="size-[17px] text-ink-4" />}
            onClick={() => signOut()}
            disabled={isSigningOut}
          >
            {isSigningOut ? "Signing out…" : "Sign out"}
          </MenuItem>
        </Menu>
      )}

      <div className="flex items-center gap-0.5 pr-2.5">
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={(event) => {
          event.stopPropagation()
          dispatch({ type: "overlay", overlay: open ? null : "account" })
        }}
        className="flex min-w-0 flex-1 items-center gap-2.5 px-4 py-3 text-left transition-colors hover:bg-foreground/[0.035]"
      >
        <Avatar initial={initial} className="size-[26px]" />
        <span className="min-w-0 flex-1 truncate text-control text-foreground">{name}</span>
        <ChevronDown className="size-4 shrink-0 text-ink-6" strokeWidth={1.7} />
      </button>
      {actions}
      </div>
    </div>
  )
}
