"use client"

import { useState, type ReactNode } from "react"
import { Brain, ChartNoAxesColumn, CircleUserRound, Search, Settings, ShieldCheck, X } from "lucide-react"

import { AppearanceSection } from "@/components/settings/appearance-section"
import { ConversationSection } from "@/components/settings/conversation-section"
import { DataSection } from "@/components/settings/data-section"
import { MemorySection } from "@/components/settings/memory-section"
import { NotificationsSection } from "@/components/settings/notifications-section"
import { ProfileSection } from "@/components/settings/profile-section"
import { SecuritySection } from "@/components/settings/security-section"
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
 * **Five panes, each a stack of titled sections.** `General` holds the product's
 * own behaviour on this browser — how it looks and moves, how a conversation
 * opens, when it may interrupt; `Account` holds who is signed in, what the
 * assistant should know about them, and how that login is secured; `Memory`
 * what the assistant was asked to keep; `Privacy` what happens to the
 * history; `Usage` what the account may spend.
 *
 * Every row does what it says. A row the product cannot honour yet is left out
 * rather than drawn inert.
 *
 * The rail switches panes rather than scrolling to anchors. Below md it folds
 * into a strip of tabs along the top, because a 200px column and a phone do not
 * both fit.
 */

type PaneId = "general" | "account" | "memory" | "privacy" | "usage"

interface Pane {
  id: PaneId
  label: string
  icon: typeof Settings
  /** Section and row words the search box should also find this pane by. */
  keywords: string
  render: () => ReactNode
}

const PANES: Pane[] = [
  {
    id: "general",
    label: "General",
    icon: Settings,
    keywords:
      "appearance color mode light dark motion animation conversation signal desk default notifications sound alert",
    render: () => (
      <>
        <AppearanceSection />
        <ConversationSection />
        <NotificationsSection />
      </>
    ),
  },
  {
    id: "account",
    label: "Account",
    icon: CircleUserRound,
    keywords:
      "profile avatar full name nickname investing style custom instructions security email password sign out device session",
    render: () => (
      <>
        <ProfileSection />
        <SecuritySection />
      </>
    ),
  },
  {
    id: "memory",
    label: "Memory",
    icon: Brain,
    keywords: "memory remembered allow delete",
    render: () => <MemorySection />,
  },
  {
    id: "privacy",
    label: "Privacy",
    icon: ShieldCheck,
    keywords: "data conversation history export download delete",
    render: () => <DataSection />,
  },
  {
    id: "usage",
    label: "Usage",
    icon: ChartNoAxesColumn,
    keywords: "usage questions cost",
    render: () => <UsageSection />,
  },
]

export function SettingsDialog() {
  const { dispatch } = useShell()
  const [selected, setSelected] = useState<PaneId>("general")
  const [term, setTerm] = useState("")

  const query = term.trim().toLowerCase()
  const matches = PANES.filter(
    (pane) =>
      query === "" || `${pane.label} ${pane.keywords}`.toLowerCase().includes(query),
  )

  // Typing past the open pane moves the content along with the rail: a pane the
  // rail no longer offers is not one the user can still be reading.
  const active = matches.some((pane) => pane.id === selected) ? selected : matches[0]?.id
  const pane = PANES.find((entry) => entry.id === active)

  return (
    <div
      onClick={(event) => event.stopPropagation()}
      className="flex h-[min(800px,100%)] w-[min(1020px,100%)] animate-vg-message-in flex-col overflow-hidden rounded-card border border-border bg-surface-raised shadow-modal md:flex-row"
    >
      <nav
        aria-label="Settings sections"
        className="scrollbar-thin flex flex-none gap-1 overflow-x-auto border-b border-border px-3 py-2 md:w-[200px] md:flex-col md:gap-px md:overflow-y-auto md:overflow-x-hidden md:border-b-0 md:border-r md:p-3"
      >
        <div className="relative hidden items-center md:flex">
          <Search
            className="pointer-events-none absolute left-2.5 size-4 text-ink-6"
            strokeWidth={1.7}
          />
          <input
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            aria-label="Search settings"
            placeholder="Search"
            className="h-8 w-full rounded-lg border border-border bg-surface-sunken pl-8 pr-2.5 text-control text-foreground outline-none transition-colors placeholder:text-ink-6 focus:border-ink-6"
          />
        </div>

        <div className="hidden px-2 pb-2 pt-6 text-micro text-ink-6 md:block">Settings</div>

        {matches.map((entry) => {
          const Icon = entry.icon
          return (
            <button
              key={entry.id}
              type="button"
              aria-current={active === entry.id ? "page" : undefined}
              onClick={() => setSelected(entry.id)}
              className={cn(
                "flex h-8 shrink-0 items-center gap-2.5 whitespace-nowrap rounded-lg px-2 text-left text-row outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring md:w-full",
                active === entry.id
                  ? "bg-foreground/[0.08] text-foreground"
                  : "text-ink-3 hover:bg-foreground/[0.045] hover:text-foreground",
              )}
            >
              <Icon className="size-4 shrink-0" strokeWidth={1.7} />
              {entry.label}
            </button>
          )
        })}

        {matches.length === 0 && (
          <p className="px-2 py-2 text-control text-ink-6">No matches.</p>
        )}
      </nav>

      {/* The close control sits outside the scrolling column so it stays put
          while a long pane scrolls under it. */}
      <div className="relative min-w-0 flex-1">
        <IconButton
          label="Close"
          onClick={() => dispatch({ type: "overlay", overlay: null })}
          className="absolute right-3 top-3 z-10 size-8"
        >
          <X className="size-4" strokeWidth={1.8} />
        </IconButton>

        {/* The rail is a nav, so the column it drives gets a name too: the
            pane's own label, which is what a reader arriving by keyboard needs
            to hear to know which pane they landed in. */}
        <div
          role="region"
          aria-label={pane?.label}
          className="scrollbar-thin h-full overflow-y-auto"
        >
          <div className="flex flex-col gap-10 px-5 pb-10 pt-14 md:px-6">{pane?.render()}</div>
        </div>
      </div>
    </div>
  )
}
