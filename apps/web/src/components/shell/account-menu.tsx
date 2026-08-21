"use client"

import {
  Check,
  ChevronDown,
  ChevronRight,
  Download,
  Globe,
  HelpCircle,
  ListChecks,
  LogOut,
  Settings,
} from "lucide-react"

import { useAuth } from "@/hooks/use-auth"

import { Menu, MenuItem, MenuSeparator } from "./primitives"
import { useShell } from "./shell-state"

/**
 * Who is signed in, and the account menu that opens from it.
 *
 * The workspace rows above the separator are the reference's own two — a team
 * and a personal space. There is no workspace resource behind them yet, so they
 * are drawn from the signed-in account and are inert: pressing one changes
 * nothing, and the surface does not pretend a switch happened.
 */
export function AccountMenu() {
  const { state, dispatch } = useShell()
  const { user, signOut, isSigningOut } = useAuth()
  const open = state.overlay === "account"

  const name = user?.full_name?.trim() || user?.email?.split("@")[0] || "Tài khoản"
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
            Cài đặt
          </MenuItem>
          <MenuItem
            icon={<Globe className="size-[17px] text-ink-4" />}
            trailing={<ChevronRight className="size-4 shrink-0 text-ink-6" />}
            disabled
          >
            Ngôn ngữ
          </MenuItem>
          <MenuItem icon={<HelpCircle className="size-[17px] text-ink-4" />} disabled>
            Trợ giúp
          </MenuItem>

          <MenuSeparator />

          <MenuItem icon={<ListChecks className="size-[17px] text-ink-4" />} disabled>
            Gói &amp; hạn mức
          </MenuItem>
          <MenuItem icon={<Download className="size-[17px] text-ink-4" />} disabled>
            Tải ứng dụng
          </MenuItem>

          <MenuSeparator />

          <MenuItem
            icon={<LogOut className="size-[17px] text-ink-4" />}
            onClick={() => signOut()}
            disabled={isSigningOut}
          >
            {isSigningOut ? "Đang đăng xuất…" : "Đăng xuất"}
          </MenuItem>
        </Menu>
      )}

      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={(event) => {
          event.stopPropagation()
          dispatch({ type: "overlay", overlay: open ? null : "account" })
        }}
        className="flex w-full items-center gap-2.5 px-4 py-3 text-left transition-colors hover:bg-foreground/[0.035]"
      >
        <Avatar initial={initial} className="size-[26px]" />
        <span className="min-w-0 flex-1 truncate text-control text-foreground">{name}</span>
        <ChevronDown className="size-4 shrink-0 text-ink-6" strokeWidth={1.7} />
      </button>
    </div>
  )
}

/**
 * The one place the amber meets the board's yellow.
 *
 * A gradient rather than a flat fill, and ink-on-light rather than the reverse:
 * it is the same reading as the filled button — a lit surface carrying dark
 * type — which is what keeps an avatar from looking like a status dot.
 */
function Avatar({ initial, className }: { initial: string; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`flex size-6 shrink-0 items-center justify-center rounded-full bg-[linear-gradient(120deg,hsl(var(--reference)),hsl(var(--primary)))] text-micro font-semibold text-surface-ground ${className ?? ""}`}
    >
      {initial}
    </span>
  )
}
