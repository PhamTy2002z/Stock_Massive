"use client"

import { useState, type ReactNode } from "react"
import { Gauge, MessagesSquare, Search, SlidersHorizontal, User, X } from "lucide-react"

import { AccountSection } from "@/components/settings/account-section"
import { AppearanceSection } from "@/components/settings/appearance-section"
import { ConversationSection } from "@/components/settings/conversation-section"
import { UsageSection } from "@/components/settings/usage-section"
import { cn } from "@/lib/utils"

import { IconButton } from "./primitives"
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
 * **Four panes in two groups, and each one has something to do.** `Cấu hình`
 * holds the two decisions a reader actually makes — how the product looks, and
 * how a new conversation opens. `Tài khoản` holds who is signed in and what
 * that account is allowed to spend. A fifth pane once carried the display
 * timezone and the exchange list as read-only text; both are answered better
 * where the numbers are, by `signal-desk/provenance-strip`, which says the
 * source, the as-of and the age of the thing on screen rather than a constant
 * in a modal the reader has to go and find.
 *
 * The rail switches panes rather than scrolling to anchors. A dialog is short
 * enough that scroll-spy would be answering a question nobody asked. Below md
 * the rail folds into a strip of tabs along the top, because a 262px column and
 * a phone do not both fit.
 */

type PaneId = "appearance" | "conversation" | "account" | "usage"

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
    id: "account",
    label: "Hồ sơ",
    group: "Tài khoản",
    icon: User,
    render: () => <AccountSection />,
  },
  {
    id: "usage",
    label: "Hạn mức",
    group: "Tài khoản",
    icon: Gauge,
    render: () => <UsageSection />,
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
      className="flex h-[min(760px,100%)] w-[min(1060px,100%)] animate-vg-message-in flex-col overflow-hidden rounded-[18px] border border-border bg-background shadow-modal md:flex-row"
    >
      <nav
        aria-label="Mục cài đặt"
        className="scrollbar-thin flex flex-none gap-1 overflow-x-auto border-b border-border bg-surface-panel px-3 py-2 md:w-[262px] md:flex-col md:gap-0 md:overflow-y-auto md:overflow-x-hidden md:border-b-0 md:border-r md:py-4"
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
            className="w-full rounded-[10px] border border-border bg-foreground/[0.03] py-2 pl-[2.1rem] pr-2.5 text-meta text-foreground outline-none transition-colors placeholder:text-ink-6 focus:border-ink-6"
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
                    "hidden px-2.5 pb-1.5 text-micro font-semibold uppercase leading-[1.3] tracking-[0.12em] text-ink-6 md:block",
                    position === 0 ? "pt-1" : "pt-4",
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
                  "flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-[9px] px-2.5 py-2 text-left text-row transition-colors md:w-full",
                  active === entry.id
                    ? "bg-surface-bubble text-foreground"
                    : "text-ink-3 hover:bg-foreground/[0.045]",
                )}
              >
                <Icon className="size-[17px] shrink-0 text-ink-4" strokeWidth={1.6} />
                {entry.label}
              </button>
            </div>
          )
        })}

        {matches.length === 0 && (
          <p className="px-2.5 py-2.5 text-row text-ink-6">Không có mục nào khớp.</p>
        )}
      </nav>

      <div className="scrollbar-thin relative min-w-0 flex-1 overflow-y-auto">
        <IconButton
          label="Đóng"
          onClick={() => dispatch({ type: "overlay", overlay: null })}
          className="absolute right-4 top-4 z-10"
        >
          <X className="size-[17px]" strokeWidth={1.8} />
        </IconButton>

        <div className="max-w-[720px] px-6 pb-11 pt-8 md:px-10">{pane?.render()}</div>
      </div>
    </div>
  )
}
