"use client"

import { BarChart3, FileText, Filter, Layers, MessageSquare, PanelLeft, Plus, Search } from "lucide-react"

import { VisgniteWordmark } from "@/components/shared/visgnite-logo"
import { useThreads } from "@/hooks/use-threads"
import { cn } from "@/lib/utils"

import { AccountMenu } from "./account-menu"
import { useDesk } from "./desk-state"
import { IconButton, QuietLine } from "./primitives"
import { SIDEBAR_WIDTH, useShell, type ShellView } from "./shell-state"
import { WatchlistSection } from "./watchlist-section"

/**
 * The left column: identity, the two main modes, and everything the user keeps.
 *
 * Collapsing is a width transition on a wrapper rather than an unmount, so the
 * Watchlist and the Thread list keep their scroll position and their queries
 * across a fold. The `aside` inside it holds a fixed 274px so its own contents
 * never reflow while the wrapper animates — a sidebar whose rows re-wrap on the
 * way out reads as breaking rather than as sliding.
 */
export function Sidebar() {
  const { state, dispatch } = useShell()
  const open = state.sidebarOpen

  return (
    <div
      className="flex-none overflow-hidden transition-[width] duration-panel ease-sidebar"
      style={{ width: open ? SIDEBAR_WIDTH : 0 }}
    >
      <aside
        aria-label="Thanh bên"
        aria-hidden={!open}
        style={{ width: SIDEBAR_WIDTH }}
        className={cn(
          "flex h-full flex-none flex-col border-r border-border bg-surface-panel",
          "transition-[opacity,transform] duration-panel ease-sidebar",
          open ? "opacity-100" : "-translate-x-4 opacity-0",
        )}
      >
        <div className="flex items-center gap-2 py-2.5 pl-[18px] pr-3.5 pt-4">
          <VisgniteWordmark />
          <div className="ml-auto flex gap-0.5">
            <IconButton label="Thu gọn thanh bên" onClick={() => dispatch({ type: "toggle-sidebar" })}>
              <PanelLeft className="size-[17px]" strokeWidth={1.6} />
            </IconButton>
            <IconButton
              label="Tìm hội thoại"
              onClick={() => dispatch({ type: "overlay", overlay: "palette" })}
            >
              <Search className="size-[17px]" strokeWidth={1.6} />
            </IconButton>
          </div>
        </div>

        <ViewSwitch />

        <Nav />

        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto scrollbar-thin">
          <WatchlistSection />

          <SectionLabel>Đã ghim</SectionLabel>
          <div className="px-2.5">
            <NavRow icon={<Layers className="size-[17px] text-primary" strokeWidth={1.6} />} disabled>
              Danh mục theo dõi
            </NavRow>
          </div>

          <SectionLabel>Hội thoại</SectionLabel>
          <ThreadList />
        </div>

        <AccountMenu />
      </aside>
    </div>
  )
}

/** The two modes the reference puts above everything else. */
function ViewSwitch() {
  const { state, dispatch } = useShell()

  const tabs: { view: ShellView; label: string; icon: React.ReactNode }[] = [
    { view: "chat", label: "Hỏi đáp", icon: <MessageSquare className="size-[15px]" strokeWidth={1.6} /> },
    { view: "board", label: "Bảng giá", icon: <BarChart3 className="size-[15px]" strokeWidth={1.6} /> },
  ]

  return (
    <div className="mx-3.5 mb-3.5 mt-1 grid grid-cols-2 gap-1 rounded-[10px] bg-foreground/[0.035] p-1">
      {tabs.map((tab) => {
        // The new-conversation screen is still the conversation mode: switching
        // to the board and back must not lose which half of the app you were in.
        const active = tab.view === "board" ? state.view === "board" : state.view !== "board"
        return (
          <button
            key={tab.view}
            type="button"
            aria-pressed={active}
            onClick={() => dispatch({ type: "view", view: tab.view })}
            className={cn(
              "relative flex items-center justify-center gap-1.5 rounded-[7px] py-2 text-control transition-colors",
              active ? "bg-accent text-foreground" : "text-ink-3 hover:text-foreground",
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

function Nav() {
  const { dispatch } = useShell()
  const desk = useDesk()

  return (
    <nav className="grid gap-px px-2.5">
      <NavRow
        icon={<Plus className="size-[17px] text-ink-4" strokeWidth={1.6} />}
        onClick={() => {
          desk.newThread()
          dispatch({ type: "view", view: "new" })
        }}
      >
        Trò chuyện mới
      </NavRow>
      {/* No screener and no saved-report resource exists yet. Drawn because the
          reference draws them, inert because pressing them would do nothing. */}
      <NavRow icon={<Filter className="size-[17px] text-ink-4" strokeWidth={1.6} />} disabled>
        Bộ lọc cổ phiếu
      </NavRow>
      <NavRow icon={<FileText className="size-[17px] text-ink-4" strokeWidth={1.6} />} disabled>
        Báo cáo đã lưu
      </NavRow>
    </nav>
  )
}

function NavRow({
  icon,
  children,
  onClick,
  disabled = false,
}: {
  icon: React.ReactNode
  children: React.ReactNode
  onClick?: () => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={disabled ? "Sắp có" : undefined}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-row transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        disabled
          ? "cursor-default text-ink-5 opacity-60"
          : "text-ink-2 hover:bg-foreground/[0.045] hover:text-foreground",
      )}
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{children}</span>
    </button>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-4 pb-1.5 pt-[18px] text-micro tracking-[0.02em] text-ink-6">
      {children}
    </div>
  )
}

/**
 * This account's Threads, newest first.
 *
 * The API answers with a title only once something has titled it, so an
 * untitled Thread is named by its own timestamp rather than by "Untitled" —
 * a list of eleven identical rows is a list of none.
 */
function ThreadList() {
  const threads = useThreads(true)
  const desk = useDesk()
  const { dispatch } = useShell()

  const rows = threads.data?.threads ?? []

  if (threads.isPending) {
    return <QuietLine>Đang tải hội thoại…</QuietLine>
  }

  if (rows.length === 0) {
    return <QuietLine>Chưa có hội thoại nào.</QuietLine>
  }

  return (
    <div className="grid flex-none content-start gap-px px-2.5 pb-2.5">
      {rows.map((row) => {
        const active = row.id === desk.threadId
        return (
          <button
            key={row.id}
            type="button"
            aria-current={active ? "true" : undefined}
            onClick={() => {
              desk.openThread(row.id)
              dispatch({ type: "view", view: "chat" })
            }}
            className={cn(
              "relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-control transition-colors",
              active
                ? "bg-foreground/[0.06] text-foreground"
                : "text-ink-3 hover:bg-foreground/[0.04] hover:text-foreground",
            )}
          >
            <i
              aria-hidden="true"
              className={cn(
                "block size-[5px] shrink-0 rounded-full",
                active ? "bg-primary" : "bg-foreground/[0.28]",
              )}
            />
            <span className="min-w-0 flex-1 truncate">{threadTitle(row.title, row.updated_at)}</span>
          </button>
        )
      })}
    </div>
  )
}

export function threadTitle(title: string | null, updatedAt: string): string {
  const trimmed = title?.trim()
  if (trimmed) return trimmed
  const moment = new Date(updatedAt)
  if (Number.isNaN(moment.getTime())) return "Hội thoại"
  return `Hội thoại ${new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(moment)}`
}
