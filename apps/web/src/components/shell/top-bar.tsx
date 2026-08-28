"use client"

import { ChevronDown, Download, Pencil, Pin, Trash2 } from "lucide-react"

import { VisgniteMark } from "@/components/shared/visgnite-logo"
import { useThreads } from "@/hooks/use-threads"
import { cn } from "@/lib/utils"

import { useDesk } from "./desk-state"
import { IconButton, Menu, MenuItem, MenuSeparator } from "./primitives"
import { threadTitle } from "./sidebar"
import { useShell } from "./shell-state"

/**
 * The bar above the main column: what you are looking at.
 *
 * The market/symbol inspector buttons and the HOSE session stamp were removed
 * with the last of the market surfaces (2026-08-26). What stays is the title
 * of the current conversation — everything else in the row belonged to lenses
 * the harness lane no longer offers. Workspace actions live in its own header.
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
      {!state.sidebarOpen && <OpenSidebarButton onClick={() => dispatch({ type: "toggle-sidebar" })} />}

      {/* The desk does not repeat the conversation's name.
          On the desk this bar sits above a ~427px column, and the name is the
          one thing on it that is neither a control nor part of what the reader
          came to look at — the list already says which conversation is open,
          one corner away. The chevron goes with it rather than being left
          naming nothing: every row in the menu it opens is inert in this
          release, so nothing reachable is lost, and switching the desk off
          brings the title and the menu back together. */}
      {!state.signalDesk && (
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
      )}

      {/* Sharing a conversation is a property of the conversation, so the
          control belongs to the bar above it — not to a panel that may not be
          open. It lived only in the desk header, which meant the reader could
          share what they were reading only while a chart happened to be beside
          it. Rendered here only while that header is absent, so the two never
          offer the same action twice on one screen. */}
      {state.inspector === null && (
        <button
          type="button"
          onClick={() => dispatch({ type: "overlay", overlay: "share" })}
          className="ml-auto shrink-0 whitespace-nowrap rounded-[9px] border border-border bg-foreground/[0.04] px-3.5 py-1.5 text-control text-ink-2 transition-colors hover:bg-foreground/[0.08] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          Chia sẻ
        </button>
      )}
    </header>
  )
}

/**
 * The mark at rest, the menu on approach.
 *
 * With the sidebar folded away the top-left corner is the only place the brand
 * appears, so the slot carries the mark rather than a bare control — and a mark
 * alone says nothing about being pressable. Hovering swaps it for three rules;
 * the affordance arrives exactly when a pointer is close enough to use it, and
 * the corner belongs to the wordmark the rest of the time.
 *
 * The swap is a crossfade between two stacked icons rather than a conditional
 * render: both are laid out from the first frame, so nothing reflows and the
 * button cannot jitter under a pointer resting on its edge. `group-focus-
 * visible` carries the same swap to the keyboard, which the pointer-only
 * reference has no way to express.
 *
 * The accessible name does not change with the hover. The reference retitles
 * the control mid-gesture, but a button that renames itself under the pointer
 * reads as two different buttons to anything that is not a pair of eyes.
 */
function OpenSidebarButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      title="Mở thanh bên"
      aria-label="Mở thanh bên"
      onClick={onClick}
      className={cn(
        "group relative flex h-[26px] w-7 flex-none animate-vg-fade-in items-center justify-center",
        "rounded-[7px] transition-colors duration-[180ms] hover:bg-foreground/[0.06]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <VisgniteMark className="h-[18px] w-3 transition-opacity duration-150 group-hover:opacity-0 group-focus-visible:opacity-0" />
      {/* Three rules of falling length — the reference's own hamburger, not the
          even-width one every icon set ships. Absolute so it shares the mark's
          centre instead of pushing it aside. */}
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className={cn(
          "absolute size-4 text-foreground opacity-0 transition-opacity duration-150",
          "group-hover:opacity-100 group-focus-visible:opacity-100",
        )}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.7}
        strokeLinecap="round"
      >
        <line x1="4" y1="7" x2="20" y2="7" />
        <line x1="4" y1="12" x2="16" y2="12" />
        <line x1="4" y1="17" x2="12" y2="17" />
      </svg>
    </button>
  )
}
