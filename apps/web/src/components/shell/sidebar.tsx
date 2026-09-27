"use client"

import * as React from "react"
import {
  ExternalLink,
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
import { FailureState } from "@/components/ui/failure-state"
import { describeFailure } from "@/lib/failure"
import { cn } from "@/lib/utils"

import { AccountMenu } from "./account-menu"
import { useDesk } from "./desk-state"
import { IconButton, Menu, MenuItem, MenuSeparator, QuietLine } from "./primitives"
import { SIDEBAR_WIDTH, sidebarFloats, useShell } from "./shell-state"

/**
 * The left column: navigation and conversation history.
 *
 * Collapsing is a width transition on a wrapper rather than an unmount, so the
 * Thread list keep their scroll position and their queries
 * across a fold. The `aside` inside it holds a fixed 274px so its own contents
 * never reflow while the wrapper animates — a sidebar whose rows re-wrap on the
 * way out reads as breaking rather than as sliding.
 */
export function Sidebar() {
  const { state, dispatch } = useShell()
  const open = state.sidebarOpen
  const floats = sidebarFloats(state)

  // Escape belongs to the floating list only. As a column it is part of the
  // workspace and there is nothing to dismiss; over the workspace it is a
  // surface laid on top, and every other one of those closes on Escape.
  React.useEffect(() => {
    if (!floats) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") dispatch({ type: "toggle-sidebar" })
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [floats, dispatch])

  if (floats) {
    return (
      <>
        {/* Dimmed rather than clear: the list is over a workspace the reader is
            still meant to see, and the wash is what says the workspace is not
            what they are pointing at. Clicking it puts the list away, which is
            the gesture every floating surface in this product answers to. */}
        <div
          aria-hidden
          onClick={() => dispatch({ type: "toggle-sidebar" })}
          className="fixed inset-0 z-[28] animate-vg-fade-in bg-background/50"
        />
        <aside
          aria-label="Thanh bên"
          style={{ width: SIDEBAR_WIDTH }}
          className="absolute inset-y-0 left-0 z-[29] flex flex-col border-r border-border bg-surface-panel shadow-sidebar motion-safe:animate-vg-sidebar-in"
        >
          <SidebarBody />
        </aside>
      </>
    )
  }

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
        <SidebarBody />
      </aside>
    </div>
  )
}

/**
 * The list itself, which is the same list either way.
 *
 * Written once and mounted by both layouts, because the difference between them
 * is where the rail sits and nothing about what is on it.
 */
function SidebarBody() {
  const { dispatch } = useShell()

  return (
    <>
      <div className="flex items-center gap-2 px-3.5 py-2.5">
        <VisgniteWordmark />
        <div className="ml-auto flex gap-0.5">
          <IconButton className="max-md:size-11" label="Thu gọn thanh bên" onClick={() => dispatch({ type: "toggle-sidebar" })}>
            <PanelLeft className="size-[17px]" strokeWidth={1.6} />
          </IconButton>
        </div>
      </div>

      <Nav />

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto scrollbar-thin">
        <Conversations />
      </div>

      <AccountMenu />
    </>
  )
}

function Nav() {
  const desk = useDesk()
  const { state, dispatch } = useShell()
  const [shortcut, setShortcut] = React.useState("Ctrl K")

  React.useEffect(() => {
    if (/Mac|iPhone|iPad/.test(navigator.platform)) setShortcut("⌘ K")
  }, [])

  return (
    <nav aria-label="Điều hướng hội thoại" className="grid gap-1 px-2.5">
      <NavRow
        icon={<Plus className="size-[17px]" aria-hidden="true" />}
        onClick={() => {
          desk.newThread()
          if (sidebarFloats(state)) dispatch({ type: "toggle-sidebar" })
        }}
      >
        Trò chuyện mới
      </NavRow>
      <NavRow
        icon={<Search className="size-[17px]" aria-hidden="true" />}
        onClick={() => dispatch({ type: "overlay", overlay: "palette" })}
        hint={shortcut}
      >
        Tìm hội thoại
      </NavRow>
    </nav>
  )
}

function NavRow({ icon, children, onClick, hint }: {
  icon: React.ReactNode
  children: React.ReactNode
  onClick: () => void
  hint?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-9 w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 [@media(pointer:coarse)]:min-h-11 text-left text-row text-ink-2 transition-colors hover:bg-foreground/[0.045] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {hint && <kbd aria-hidden="true" className="hidden text-micro text-ink-5 md:inline">{hint}</kbd>}
    </button>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-3.5 pb-1 pt-3 text-micro tracking-[0.02em] text-ink-6">
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
  const { dispatch } = useShell()
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
      {pinned.length > 0 && (
        <>
          <SectionLabel>Đã ghim</SectionLabel>
          <div className="grid flex-none content-start gap-px px-2.5">
            {pinned.map((row) => <ThreadRow key={row.id} row={row} {...rowProps} />)}
          </div>
        </>
      )}

      <SectionLabel>Gần đây</SectionLabel>
      {threads.isPending ? (
        <QuietLine>Đang tải hội thoại…</QuietLine>
      ) : threads.isError ? (
        // A list that failed to load is not an empty list, and this is the one
        // place in the product where confusing the two reads as *data loss*: a
        // reader whose rail says "Chưa có hội thoại nào" after a dropped
        // request believes their history is gone. It says what happened and
        // offers the one thing that fixes it.
        <div className="px-2.5">
          <FailureState
            failure={describeFailure(threads.error)}
            density="inline"
            onRetry={() => void threads.refetch()}
          />
        </div>
      ) : rest.length === 0 ? (
        <QuietLine>
          {pinned.length === 0 ? "Chưa có hội thoại nào." : "Tất cả hội thoại đang được ghim."}
        </QuietLine>
      ) : (
        <div className="grid grid-cols-fit flex-none content-start gap-px px-2.5 pb-2.5">
          {rest.slice(0, 20).map((row) => (
            <ThreadRow key={row.id} row={row} {...rowProps} />
          ))}
        </div>
      )}
      {rest.length > 20 && (
        <div className="px-2.5 pb-2.5">
          <button
            type="button"
            onClick={() => dispatch({ type: "overlay", overlay: "palette" })}
            className="min-h-9 rounded-lg px-2.5 py-1.5 [@media(pointer:coarse)]:min-h-11 text-row text-ink-4 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Xem tất cả
          </button>
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
  const { state, dispatch } = useShell()
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
          if (sidebarFloats(state)) dispatch({ type: "toggle-sidebar" })
        }}
        className={cn(
          "flex min-h-9 w-full items-center gap-2.5 rounded-lg py-1.5 pl-2.5 pr-9 [@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:pr-12 text-left text-control transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
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
          "absolute right-0 top-1/2 -translate-y-1/2 [@media(pointer:coarse)]:size-11",
          open ? "opacity-100" : "opacity-100 md:opacity-0 focus-visible:opacity-100 group-hover/row:opacity-100 [@media(hover:none)]:opacity-100",
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
 * The menu itself.
 *
 * Delete takes effect on the press: the menu is only reachable behind the
 * ellipsis, so the item is already two deliberate gestures deep, and a second
 * confirmation there was ceremony over a list users clean out routinely.
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
  return (
    <Menu className="absolute right-1 top-[calc(100%-4px)] z-30 w-[212px]">
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
      <MenuItem icon={<Trash2 className="size-[17px]" />} destructive onClick={onDelete}>
        Xoá
      </MenuItem>
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
export function RenameField({
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
