"use client"

/**
 * The Signal Desk's own chrome: which board is open, and the way out to a file.
 *
 * **One control names the board; a dropdown under it holds the rest.** The
 * surface used to draw a tab per board, and a conversation twenty boards long
 * became a strip of clipped titles the reader scrolled sideways through. Now the
 * header says what is on screen and the dropdown offers everything else — pinned
 * first, then newest — with the searchable switcher as its last row.
 *
 * **"Nguồn" is a sibling toggle, not a second panel.** What an answer rested on
 * and what it was drawn from are the same question asked from two sides, and a
 * reader comparing a figure with its source should not have to give up half the
 * screen to see the other.
 *
 * **There is no "Lưu".** The design draws one beside the export and there is no
 * endpoint behind it — the sidebar's "Báo cáo đã lưu" is still "Sắp ra mắt". A
 * control that swallowed the press would tell a reader their work was kept.
 *
 * **Only the export waits for a board.** "Nguồn" and "Chia sẻ" do not: sources
 * are what an *answer* rested on and sharing is of the *conversation*, so a
 * reader who asked a question in Chat and got a cited answer has something for
 * both of them with no board anywhere in sight. Dimming the pair on an empty
 * desk read as tidy and was simply wrong about what they act on.
 */

import { ChevronDown, Download, Link2, PanelTop } from "lucide-react"

import type { SignalDeskBoard } from "@/components/shell/shell-state"
import { BOARD_SWITCHER_COPY, SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"

import { BoardMenu } from "./board-menu"

export function SignalDeskHeader({
  boards,
  pinned,
  activeDeskViewId,
  showingSources,
  canExport,
  menuOpen,
  onOpenDeskView,
  onOpenSources,
  onToggleMenu,
  onTogglePin,
  onOpenSwitcher,
  onShare,
  onExport,
}: {
  /** Every board of the conversation, oldest first. */
  boards: SignalDeskBoard[]
  /** The pinned ids, in pin order. */
  pinned: string[]
  activeDeskViewId: string | null
  showingSources: boolean
  /** False until the numbers are in the browser: there is nothing to write yet. */
  canExport: boolean
  /** Whether the dropdown is open; the shell owns it like every other overlay. */
  menuOpen: boolean
  onOpenDeskView: (artifactId: string) => void
  onOpenSources: () => void
  onToggleMenu: (open: boolean) => void
  onTogglePin: (artifactId: string, pinned: boolean) => void
  /** The searchable switcher, reached from the dropdown's last row and ⌘K. */
  onOpenSwitcher: () => void
  onShare: () => void
  onExport: () => void
}) {
  const active = boards.find((board) => board.artifactId === activeDeskViewId)
  const label = active?.title ?? BOARD_SWITCHER_COPY.choose

  return (
    <header className="flex flex-none items-center gap-2 px-3.5 pt-2.5">
      <div className="relative min-w-0 flex-1">
        <button
          type="button"
          aria-label={BOARD_SWITCHER_COPY.open}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          onClick={() => onToggleMenu(!menuOpen)}
          className={cn(
            "flex max-w-full items-center gap-1.5 rounded-[9px] px-2 py-1.5 text-control transition-colors hover:bg-foreground/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            showingSources ? "text-ink-5" : "text-ink-1",
            menuOpen && "bg-foreground/[0.06]",
          )}
        >
          <PanelTop className="size-[13px] flex-none text-ink-5" strokeWidth={1.7} aria-hidden />
          <span className="min-w-0 truncate">{label}</span>
          {boards.length > 1 && (
            <span className="flex-none text-micro text-ink-6">
              {BOARD_SWITCHER_COPY.count(boards.length)}
            </span>
          )}
          <ChevronDown className="size-3 flex-none text-ink-5" strokeWidth={2} aria-hidden />
        </button>
        {menuOpen && (
          <BoardMenu
            boards={boards}
            pinned={pinned}
            activeBoardId={showingSources ? null : activeDeskViewId}
            onOpenBoard={onOpenDeskView}
            onTogglePin={onTogglePin}
            onSearch={onOpenSwitcher}
            onClose={() => onToggleMenu(false)}
          />
        )}
      </div>

      <div className="flex flex-none items-center gap-2">
        <button
          type="button"
          aria-pressed={showingSources}
          onClick={onOpenSources}
          className={cn(
            "flex items-center gap-1.5 rounded-[9px] px-2.5 py-1.5 text-control transition-colors hover:bg-foreground/[0.06]",
            showingSources ? "bg-foreground/[0.06] text-ink-1" : "text-ink-5 hover:text-ink-2",
          )}
        >
          <Link2 className="size-[13px] flex-none" strokeWidth={1.7} aria-hidden />
          <span>{SIGNAL_DESK_COPY.sources}</span>
        </button>
        <button
          type="button"
          onClick={onShare}
          className="shrink-0 whitespace-nowrap rounded-[9px] px-3 py-1.5 text-control text-ink-3 transition-colors hover:bg-foreground/[0.06] hover:text-ink-1"
        >
          Chia sẻ
        </button>
        <button
          type="button"
          onClick={onExport}
          disabled={!canExport}
          // The one solid shape in this header, and it lifts on hover: it is the
          // only control here that leaves the application, so it is the only one
          // that acknowledges the press before the browser takes over.
          className="inline-flex items-center gap-1.5 rounded-full bg-foreground px-3 py-1.5 text-meta font-medium text-background transition-[transform,filter] duration-150 hover:-translate-y-px hover:brightness-110 disabled:pointer-events-none disabled:opacity-40 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
        >
          <Download className="size-3.5" strokeWidth={1.6} aria-hidden />
          {SIGNAL_DESK_COPY.export}
        </button>
      </div>
    </header>
  )
}
