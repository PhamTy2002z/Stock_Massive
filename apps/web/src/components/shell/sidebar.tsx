"use client"

import * as React from "react"
import {
  BarChart3,
  ExternalLink,
  FileText,
  Filter,
  Layers,
  MessageSquare,
  MoreVertical,
  PanelLeft,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Search,
  Trash2,
} from "lucide-react"

import { VisgniteWordmark } from "@/components/shared/visgnite-logo"
import { useDeleteThread, useThreads, useUpdateThread } from "@/hooks/use-threads"
import type { Thread } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"

import { AccountMenu } from "./account-menu"
import { useDesk } from "./desk-state"
import { IconButton, Menu, MenuItem, MenuSeparator, QuietLine } from "./primitives"
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

          <Conversations />
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
    <nav className="grid grid-cols-fit gap-px px-2.5">
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
 * This account's Threads: the pinned ones, then the rest.
 *
 * The API answers with a title only once something has titled it, so an
 * untitled Thread is named by its own timestamp rather than by "Untitled" —
 * a list of eleven identical rows is a list of none.
 *
 * **The two groups are a split of one ordered list, never a re-sort.** The
 * backend already answers with the pinned group first and each group by last
 * touched; partitioning on `pinned_at` keeps both sections in that order while
 * leaving one authority on what the order is.
 *
 * The open menu and the row being renamed are held here rather than in each
 * row, because both are singular: opening a second menu closes the first, and
 * a rename in flight elsewhere would be a text field the user cannot see.
 */
export function Conversations() {
  const threads = useThreads(true)
  const [menuFor, setMenuFor] = React.useState<string | null>(null)
  const [renamingId, setRenamingId] = React.useState<string | null>(null)

  const rows = threads.data?.threads ?? []
  const pinned = rows.filter((row) => row.pinned_at !== null)
  const rest = rows.filter((row) => row.pinned_at === null)

  const rowProps = {
    menuFor,
    onMenu: setMenuFor,
    renamingId,
    onRename: setRenamingId,
  }

  return (
    <>
      <SectionLabel>Đã ghim</SectionLabel>
      <div className="grid flex-none content-start gap-px px-2.5">
        <NavRow icon={<Layers className="size-[17px] text-primary" strokeWidth={1.6} />} disabled>
          Danh mục theo dõi
        </NavRow>
        {pinned.map((row) => (
          <ThreadRow key={row.id} row={row} {...rowProps} />
        ))}
      </div>

      <SectionLabel>Hội thoại</SectionLabel>
      {threads.isPending ? (
        <QuietLine>Đang tải hội thoại…</QuietLine>
      ) : rest.length === 0 ? (
        <QuietLine>
          {pinned.length === 0 ? "Chưa có hội thoại nào." : "Tất cả hội thoại đang được ghim."}
        </QuietLine>
      ) : (
        <div className="grid flex-none content-start gap-px px-2.5 pb-2.5">
          {rest.map((row) => (
            <ThreadRow key={row.id} row={row} {...rowProps} />
          ))}
        </div>
      )}
    </>
  )
}

/**
 * One Thread, and the four things the menu does to it.
 *
 * The menu button is a sibling of the row rather than nested in it: a button
 * inside a button is invalid, and the nesting is what would make a press on the
 * ellipsis also open the conversation behind it.
 *
 * Rename replaces the row with a text field in place. A dialog would take the
 * user out of the list to change one word, and the field is the same shape and
 * position as the row it stands in for, so nothing moves under the cursor.
 */
function ThreadRow({
  row,
  menuFor,
  onMenu,
  renamingId,
  onRename,
}: {
  row: Thread
  menuFor: string | null
  onMenu: (id: string | null) => void
  renamingId: string | null
  onRename: (id: string | null) => void
}) {
  const desk = useDesk()
  const { dispatch } = useShell()
  const update = useUpdateThread()
  const remove = useDeleteThread()
  const container = React.useRef<HTMLDivElement>(null)

  const open = menuFor === row.id
  const active = row.id === desk.threadId
  const pinned = row.pinned_at !== null
  const name = threadTitle(row.title, row.updated_at)

  // Dismissal is on the document because the menu floats over rows it is not a
  // child of, so a press anywhere else has to close it — including a press on
  // another row's ellipsis, which opens that one in the same gesture.
  React.useEffect(() => {
    if (!open) return
    function onPointerDown(event: MouseEvent) {
      if (!container.current?.contains(event.target as Node)) onMenu(null)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onMenu(null)
    }
    document.addEventListener("mousedown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("mousedown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [open, onMenu])

  if (renamingId === row.id) {
    return (
      <RenameField
        row={row}
        onDone={(title) => {
          onRename(null)
          if (title !== null && title !== (row.title ?? "")) {
            update.mutate({ threadId: row.id, title })
          }
        }}
      />
    )
  }

  return (
    <div ref={container} className="group/row relative">
      <button
        type="button"
        aria-current={active ? "true" : undefined}
        onClick={() => {
          desk.openThread(row.id)
          dispatch({ type: "view", view: "chat" })
        }}
        className={cn(
          "flex w-full items-center gap-2.5 rounded-lg py-2 pl-2.5 pr-9 text-left text-control transition-colors",
          active
            ? "bg-foreground/[0.06] text-foreground"
            : "text-ink-3 hover:bg-foreground/[0.04] hover:text-foreground",
        )}
      >
        {pinned ? (
          <Pin className="size-[11px] shrink-0 text-primary" strokeWidth={2} aria-hidden="true" />
        ) : (
          <i
            aria-hidden="true"
            className={cn(
              "block size-[5px] shrink-0 rounded-full",
              active ? "bg-primary" : "bg-foreground/[0.28]",
            )}
          />
        )}
        <span className="min-w-0 flex-1 truncate">{name}</span>
      </button>

      {/* Always in the DOM and revealed on hover or focus. Mounting it on hover
          would put the control out of reach of a keyboard entirely, and make it
          jump into existence under a pointer that had already arrived. */}
      <IconButton
        label={`Tuỳ chọn cho ${name}`}
        size="sm"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => onMenu(open ? null : row.id)}
        className={cn(
          "absolute right-1 top-1/2 -translate-y-1/2",
          open ? "opacity-100" : "opacity-0 focus-visible:opacity-100 group-hover/row:opacity-100",
        )}
      >
        <MoreVertical className="size-[15px]" strokeWidth={1.7} />
      </IconButton>

      {open && (
        <ThreadMenu
          row={row}
          pinned={pinned}
          onPin={() => {
            onMenu(null)
            update.mutate({ threadId: row.id, pinned: !pinned })
          }}
          onRename={() => {
            onMenu(null)
            onRename(row.id)
          }}
          onDelete={() => {
            onMenu(null)
            remove.mutate(row.id, {
              // The conversation on screen cannot survive its own Thread. Every
              // other row keeps whatever it was doing.
              onSuccess: () => {
                if (active) desk.newThread()
              },
            })
          }}
        />
      )}
    </div>
  )
}

/**
 * The menu itself, with Delete behind a second press.
 *
 * The confirmation is the menu's own state rather than a dialog: a Thread and
 * its transcript are not recoverable, and a destructive item one press away in
 * a list of hover-revealed controls is the wrong distance — but a modal for it
 * would be the wrong ceremony, and it would take focus off the list.
 */
function ThreadMenu({
  row,
  pinned,
  onPin,
  onRename,
  onDelete,
}: {
  row: Thread
  pinned: boolean
  onPin: () => void
  onRename: () => void
  onDelete: () => void
}) {
  const [confirming, setConfirming] = React.useState(false)

  return (
    <Menu className="absolute right-1 top-[calc(100%-4px)] z-30 w-[212px]">
      {confirming ? (
        <>
          <p className="px-2.5 pb-1 pt-1.5 text-meta leading-relaxed text-ink-4">
            Xoá hội thoại này và toàn bộ nội dung của nó? Không khôi phục được.
          </p>
          <MenuItem icon={<Trash2 className="size-[17px]" />} destructive onClick={onDelete}>
            Xoá vĩnh viễn
          </MenuItem>
          <MenuItem onClick={() => setConfirming(false)}>Huỷ</MenuItem>
        </>
      ) : (
        <>
          <MenuItem
            icon={
              pinned ? (
                <PinOff className="size-[17px] text-ink-4" />
              ) : (
                <Pin className="size-[17px] text-ink-4" />
              )
            }
            onClick={onPin}
          >
            {pinned ? "Bỏ ghim" : "Ghim"}
          </MenuItem>
          <MenuItem icon={<Pencil className="size-[17px] text-ink-4" />} onClick={onRename}>
            Đổi tên
          </MenuItem>
          {/* A plain link, so the browser's own "open in new tab" affordances —
              middle click, ⌘-click — work on it as well as the item itself. */}
          <a href={`/?thread=${encodeURIComponent(row.id)}`} target="_blank" rel="noopener" className="block">
            <MenuItem icon={<ExternalLink className="size-[17px] text-ink-4" />}>
              Mở ở tab mới
            </MenuItem>
          </a>

          <MenuSeparator />

          <MenuItem
            icon={<Trash2 className="size-[17px]" />}
            destructive
            onClick={() => setConfirming(true)}
          >
            Xoá
          </MenuItem>
        </>
      )}
    </Menu>
  )
}

/**
 * The row, as a text field.
 *
 * Enter and blur both commit, Escape abandons — the three endings a rename in a
 * list has. Committing on blur rather than discarding, because the user typed
 * the name they wanted and clicking away is not a retraction.
 */
function RenameField({
  row,
  onDone,
}: {
  row: Thread
  onDone: (title: string | null) => void
}) {
  const [draft, setDraft] = React.useState(row.title ?? "")
  // Held so Escape's blur cannot commit the value Escape just abandoned.
  const abandoned = React.useRef(false)

  return (
    <input
      autoFocus
      value={draft}
      aria-label={`Đổi tên ${threadTitle(row.title, row.updated_at)}`}
      onChange={(event) => setDraft(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.currentTarget.blur()
        } else if (event.key === "Escape") {
          abandoned.current = true
          event.currentTarget.blur()
        }
      }}
      onBlur={() => onDone(abandoned.current ? null : draft.trim())}
      className={cn(
        "w-full rounded-lg border border-primary/40 bg-surface-sunken px-2.5 py-2 text-control text-foreground",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    />
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
