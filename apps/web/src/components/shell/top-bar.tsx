"use client"

import { useEffect, useState } from "react"
import { BarChart3, ChevronDown, Download, LineChart, PanelLeft, Pencil, Pin, Trash2 } from "lucide-react"

import { useThreads } from "@/hooks/use-threads"
import { getMarketSession } from "@/lib/market-session"
import { cn } from "@/lib/utils"

import { useDesk } from "./desk-state"
import { IconButton, Menu, MenuItem, MenuSeparator } from "./primitives"
import { threadTitle } from "./sidebar"
import { useShell } from "./shell-state"

/**
 * The bar above the main column: what you are looking at, and the two panels.
 *
 * The session stamp is dropped rather than truncated once the inspector has
 * taken enough width — it is the least load-bearing thing in the row, and a
 * header that wraps is a header that has stopped being one.
 */
export function TopBar() {
  const { state, dispatch, panelWidth } = useShell()
  const desk = useDesk()
  const threads = useThreads(true)

  const current = threads.data?.threads.find((row) => row.id === desk.threadId)
  const title =
    state.view === "board"
      ? "Bảng giá thị trường"
      : desk.threadId === null
        ? "Trò chuyện mới"
        : current
          ? threadTitle(current.title, current.updated_at)
          : "Hội thoại"

  // 1100px of main column is where the reference stops showing the stamp.
  const showStamp = state.viewport > 0 && state.viewport - panelWidth > 1100
  const menuOpen = state.overlay === "thread"

  return (
    <header className="flex flex-none items-center gap-2 px-5 py-3">
      {!state.sidebarOpen && (
        <IconButton
          label="Mở thanh bên"
          onClick={() => dispatch({ type: "toggle-sidebar" })}
          className="animate-vg-fade-in"
        >
          <PanelLeft className="size-[17px]" strokeWidth={1.6} />
        </IconButton>
      )}

      <div className="relative flex min-w-0 items-center gap-1">
        <h1 className="min-w-0 truncate text-[0.95rem] font-normal text-ink-2">{title}</h1>
        <IconButton
          label="Tuỳ chọn hội thoại"
          size="sm"
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          onClick={(event) => {
            event.stopPropagation()
            dispatch({ type: "overlay", overlay: menuOpen ? null : "thread" })
          }}
          className="rounded-[7px]"
        >
          <ChevronDown className="size-[15px]" strokeWidth={1.7} />
        </IconButton>

        {menuOpen && (
          <Menu className="absolute left-0 top-[34px] min-w-[236px] rounded-xl">
            {/* Pinning, renaming, exporting and deleting a Thread each need an
                endpoint the API does not expose yet — the transport creates,
                lists and reads Threads and nothing more. Drawn and inert rather
                than hidden, so the shape of the menu matches the reference. */}
            <MenuItem icon={<Pin className="size-4 text-ink-4" strokeWidth={1.6} />} hint="P" disabled>
              Ghim
            </MenuItem>
            <MenuItem icon={<Pencil className="size-4 text-ink-4" strokeWidth={1.6} />} hint="R" disabled>
              Đổi tên
            </MenuItem>
            <MenuItem icon={<Download className="size-4 text-ink-4" strokeWidth={1.6} />} hint="E" disabled>
              Xuất PDF
            </MenuItem>
            <MenuSeparator />
            <MenuItem icon={<Trash2 className="size-4" strokeWidth={1.6} />} hint="D" destructive disabled>
              Xoá
            </MenuItem>
          </Menu>
        )}
      </div>

      <div className="ml-auto flex items-center gap-2">
        <PanelButton
          label="Thị trường"
          icon={<BarChart3 className="size-[15px]" strokeWidth={1.6} />}
          active={state.inspector === "market"}
          onClick={() => dispatch({ type: "open-inspector", tab: "market" })}
        />
        <PanelButton
          label="Chi tiết mã"
          icon={<LineChart className="size-[15px]" strokeWidth={1.6} />}
          active={state.inspector === "symbol"}
          onClick={() => dispatch({ type: "open-inspector", tab: "symbol" })}
        />

        {showStamp && <SessionStamp />}

        <button
          type="button"
          onClick={() => dispatch({ type: "overlay", overlay: "share" })}
          className="shrink-0 whitespace-nowrap rounded-[9px] border border-border bg-foreground/[0.04] px-3.5 py-1.5 text-control text-ink-2 transition-colors hover:bg-foreground/[0.08]"
        >
          Chia sẻ
        </button>
      </div>
    </header>
  )
}

function PanelButton({
  label,
  icon,
  active,
  onClick,
}: {
  label: string
  icon: React.ReactNode
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={label}
      className={cn(
        "flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[9px] border border-border px-2.5 py-1.5 text-meta transition-colors",
        active
          ? "bg-foreground/[0.08] text-foreground"
          : "text-ink-4 hover:bg-foreground/[0.06] hover:text-foreground",
      )}
    >
      {icon}
      <span className="hidden md:inline">{label}</span>
    </button>
  )
}

/**
 * Which phase of the HOSE session the clock is in, from the clock alone.
 *
 * Rendered only after mount: the phase is read from the viewer's own moment,
 * and a server that stamped "đã đóng cửa" into HTML a browser hydrates at
 * 10:30 would be a mismatch rather than a stale label.
 */
function SessionStamp() {
  const [session, setSession] = useState<ReturnType<typeof getMarketSession> | null>(null)

  useEffect(() => {
    const tick = () => setSession(getMarketSession())
    tick()
    const timer = window.setInterval(tick, 30_000)
    return () => window.clearInterval(timer)
  }, [])

  if (session === null) return null

  return (
    <span className="flex items-center gap-1.5 whitespace-nowrap font-mono text-micro text-ink-6">
      <i
        aria-hidden="true"
        className={cn(
          "block size-[5px] rounded-full",
          session.isLive ? "bg-positive" : "bg-ink-6",
        )}
      />
      HOSE · {session.label}
    </span>
  )
}
