"use client"

import { useState, type ReactNode } from "react"
import {
  Bell,
  Database,
  Gauge,
  MessagesSquare,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  User,
  X,
} from "lucide-react"

import { AppearanceSection } from "@/components/settings/appearance-section"
import { ConversationSection } from "@/components/settings/conversation-section"
import { DataSection } from "@/components/settings/data-section"
import { NotificationsSection } from "@/components/settings/notifications-section"
import { ProfileSection } from "@/components/settings/profile-section"
import { SecuritySection } from "@/components/settings/security-section"
import { UsageSection } from "@/components/settings/usage-section"
import { useAuth } from "@/hooks/use-auth"
import { cn } from "@/lib/utils"

import { Avatar, IconButton } from "./primitives"
import { useShell } from "./shell-state"

/**
 * Settings, over the workspace rather than instead of it.
 *
 * It used to be a route, which meant leaving the shell — the conversation, the
 * inspector and a half-typed question all torn down — to change a colour mode.
 * That is not worth a navigation, so the whole surface is a dialog: the
 * workspace stays mounted behind the scrim and closing puts the user back
 * exactly where they were.
 *
 * **Seven panes in two groups.** `Cấu hình` holds the decisions about the
 * product's own behaviour — how it looks, how a conversation opens, when it is
 * allowed to interrupt. `Tài khoản` holds who is signed in, what that account
 * may spend, how it is secured and what happens to its history.
 *
 * Much of it is not built yet, and the surface says which parts. Every row with
 * no write path behind it carries `soon` — a badge beside the label, an inert
 * control — rather than being left out: the panes are the product's own
 * commitments, and a reader looking for two-factor is better served by "not
 * yet" than by a dialog that never mentions it. The two panes that are entirely
 * live, `Giao diện` and `Hạn mức`, sit at the top of their groups so the first
 * thing the reader meets is something that works.
 *
 * The rail switches panes rather than scrolling to anchors. A dialog is short
 * enough that scroll-spy would be answering a question nobody asked. Below md
 * the rail folds into a strip of tabs along the top, because a 236px column and
 * a phone do not both fit — and the account card at its foot goes with it,
 * since the same identity is already on screen in the shell behind.
 */

type PaneId =
  | "appearance"
  | "conversation"
  | "notifications"
  | "profile"
  | "usage"
  | "security"
  | "data"

interface Pane {
  id: PaneId
  label: string
  group: string
  icon: typeof SlidersHorizontal
  render: () => ReactNode
}

const PANES: Pane[] = [
  {
    id: "appearance",
    label: "Giao diện",
    group: "Cấu hình",
    icon: SlidersHorizontal,
    render: () => <AppearanceSection />,
  },
  {
    id: "conversation",
    label: "Hội thoại",
    group: "Cấu hình",
    icon: MessagesSquare,
    render: () => <ConversationSection />,
  },
  {
    id: "notifications",
    label: "Thông báo",
    group: "Cấu hình",
    icon: Bell,
    render: () => <NotificationsSection />,
  },
  {
    id: "profile",
    label: "Hồ sơ",
    group: "Tài khoản",
    icon: User,
    render: () => <ProfileSection />,
  },
  {
    id: "usage",
    label: "Hạn mức",
    group: "Tài khoản",
    icon: Gauge,
    render: () => <UsageSection />,
  },
  {
    id: "security",
    label: "Bảo mật",
    group: "Tài khoản",
    icon: ShieldCheck,
    render: () => <SecuritySection />,
  },
  {
    id: "data",
    label: "Dữ liệu",
    group: "Tài khoản",
    icon: Database,
    render: () => <DataSection />,
  },
]

export function SettingsDialog() {
  const { dispatch } = useShell()
  const [selected, setSelected] = useState<PaneId>("appearance")
  const [term, setTerm] = useState("")

  const query = term.trim().toLowerCase()
  const matches = PANES.filter(
    (pane) => query === "" || pane.label.toLowerCase().includes(query),
  )

  // Typing past the open pane moves the content along with the rail: a pane the
  // rail no longer offers is not one the user can still be reading.
  const active = matches.some((pane) => pane.id === selected) ? selected : matches[0]?.id
  const pane = PANES.find((entry) => entry.id === active)

  return (
    <div
      onClick={(event) => event.stopPropagation()}
      className="flex h-[min(700px,100%)] w-[min(1060px,100%)] animate-vg-message-in flex-col overflow-hidden rounded-[18px] border border-border bg-surface-raised shadow-modal md:flex-row"
    >
      <nav
        aria-label="Mục cài đặt"
        className="scrollbar-thin flex flex-none gap-1 overflow-x-auto border-b border-border bg-surface-panel px-3 py-2 md:w-[236px] md:flex-col md:gap-0 md:overflow-y-auto md:overflow-x-hidden md:border-b-0 md:border-r md:px-3 md:py-4"
      >
        <h2 className="hidden px-2 pb-3 pt-1.5 text-[1.02rem] font-medium tracking-[-0.015em] md:block">
          Cài đặt
        </h2>

        <div className="relative mx-1 mb-3.5 hidden items-center md:flex">
          <Search
            className="pointer-events-none absolute left-2.5 size-[15px] text-ink-6"
            strokeWidth={1.7}
          />
          <input
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            aria-label="Tìm cài đặt"
            placeholder="Tìm cài đặt"
            className="w-full rounded-[10px] border border-border bg-surface-sunken py-2 pl-[2.1rem] pr-2.5 text-control text-foreground outline-none transition-colors placeholder:text-ink-6 focus:border-ink-6"
          />
        </div>

        {matches.map((entry, position) => {
          const Icon = entry.icon
          const opensGroup = matches[position - 1]?.group !== entry.group

          return (
            <div key={entry.id} className="contents md:block">
              {opensGroup && (
                <div
                  className={cn(
                    "hidden px-2.5 pb-1.5 text-micro font-semibold uppercase leading-[1.3] tracking-[0.13em] text-ink-6 md:block",
                    position === 0 ? "pt-1" : "pt-[18px]",
                  )}
                >
                  {entry.group}
                </div>
              )}
              <button
                type="button"
                aria-current={active === entry.id ? "page" : undefined}
                onClick={() => setSelected(entry.id)}
                className={cn(
                  "mt-[3px] flex shrink-0 items-center gap-[0.6rem] whitespace-nowrap rounded-[10px] px-2.5 py-2 text-left text-row transition-colors md:w-full",
                  active === entry.id
                    ? "bg-foreground/[0.08] text-foreground"
                    : "text-ink-4 hover:bg-foreground/[0.045] hover:text-foreground",
                )}
              >
                <Icon className="size-[15px] shrink-0" strokeWidth={1.7} />
                {entry.label}
              </button>
            </div>
          )
        })}

        {matches.length === 0 && (
          <p className="px-2.5 py-2.5 text-row text-ink-6">Không có mục nào khớp.</p>
        )}

        <AccountCard />
      </nav>

      {/* The rail is a nav, so the column it drives gets a name too: the pane's
          own title, which is what a reader arriving here by keyboard needs to
          hear to know which of the seven they landed in. */}
      <div
        role="region"
        aria-label={pane?.label}
        className="scrollbar-thin relative min-w-0 flex-1 overflow-y-auto"
      >
        <IconButton
          label="Đóng"
          onClick={() => dispatch({ type: "overlay", overlay: null })}
          className="absolute right-4 top-4 z-10"
        >
          <X className="size-[15px]" strokeWidth={1.8} />
        </IconButton>

        <div className="max-w-[720px] px-6 pb-11 pt-[34px] md:px-11">{pane?.render()}</div>
      </div>
    </div>
  )
}

/**
 * Whose settings these are, at the foot of the rail.
 *
 * The dialog covers the shell, so the identity that was on screen a moment ago
 * is now behind a scrim — and every pane in the lower group is *about* that
 * account. `mt-auto` rather than a fixed position: on a short viewport the rail
 * scrolls and the card goes with it, where a pinned footer would sit on top of
 * the last pane in the list.
 */
function AccountCard() {
  const { user } = useAuth()

  const name = user?.full_name?.trim() || user?.email?.split("@")[0] || "Tài khoản"
  const initial = name.charAt(0).toUpperCase()

  return (
    <div className="mt-auto hidden items-center gap-[0.6rem] rounded-xl border border-hairline bg-surface-sunken px-3 py-[0.6rem] md:mt-auto md:flex">
      <Avatar initial={initial} className="size-7 text-meta" />
      <span className="min-w-0">
        <span className="block truncate text-control text-foreground">{name}</span>
        <span className="block truncate text-micro text-ink-6">{user?.email ?? "—"}</span>
      </span>
    </div>
  )
}
