"use client"

import { ChevronDown, Download, PanelLeft, Pencil, Pin, Trash2 } from "lucide-react"

import { useThreads } from "@/hooks/use-threads"

import { useDesk } from "./desk-state"
import { IconButton, Menu, MenuItem, MenuSeparator } from "./primitives"
import { threadTitle } from "./sidebar"
import { useShell } from "./shell-state"

/**
 * The bar above the main column: what you are looking at, and the share action.
 *
 * The market/symbol inspector buttons and the HOSE session stamp were removed
 * with the last of the market surfaces (2026-08-26). What stays is the title
 * of the current conversation and the share affordance — everything else in
 * the row belonged to lenses the harness lane no longer offers.
 */
export function TopBar() {
  const { state, dispatch } = useShell()
  const desk = useDesk()
  const threads = useThreads(true)

  const current = threads.data?.threads.find((row) => row.id === desk.threadId)
  const title =
    state.view === "news"
      ? "Tin tức thị trường"
      : state.view === "board"
        ? "Bảng giá thị trường"
        : desk.threadId === null
          ? "Trò chuyện mới"
          : current
            ? threadTitle(current.title, current.updated_at)
            : "Hội thoại"

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
