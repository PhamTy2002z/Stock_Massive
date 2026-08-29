"use client"

import * as React from "react"
import { ChevronDown, EyeOff, Pencil, Pin, PinOff, Trash2 } from "lucide-react"

import { VisgniteMark } from "@/components/shared/visgnite-logo"
import { useDeleteThread, useThreads, useUpdateThread } from "@/hooks/use-threads"
import { cn } from "@/lib/utils"

import { useDesk } from "./desk-state"
import { IconButton, Menu, MenuItem, MenuSeparator } from "./primitives"
import { RenameField, threadTitle } from "./sidebar"
import { useShell } from "./shell-state"

/**
 * The bar above the main column: what you are looking at.
 *
 * The market/symbol inspector buttons and the HOSE session stamp were removed
 * with the last of the market surfaces (2026-08-26). What stays is the title
 * of the current conversation — everything else in the row belonged to lenses
 * the harness lane no longer offers. Workspace actions live in its own header.
 *
 * The menu behind the chevron writes for real. It was drawn inert against an
 * API that "creates, lists and reads Threads and nothing more" — a sentence
 * that stopped being true once the sidebar's own menu started pinning,
 * renaming and deleting through `PATCH` and `DELETE`. Both menus now act on
 * the same three endpoints, so the same gesture means the same thing whichever
 * corner the reader reaches for.
 */
export function TopBar() {
  const { state, dispatch } = useShell()
  const desk = useDesk()
  const threads = useThreads(true)
  const update = useUpdateThread()
  const remove = useDeleteThread()
  const [renaming, setRenaming] = React.useState(false)

  const current = threads.data?.threads.find((row) => row.id === desk.threadId)
  const fullTitle =
    state.view === "news"
      ? "Tin tức thị trường"
      : state.view === "board"
        ? "Bảng giá thị trường"
        : desk.threadId === null
          ? "Trò chuyện mới"
          : current
            ? threadTitle(current.title, current.updated_at)
            : "Hội thoại"
  const title = shorten(fullTitle)

  const menuOpen = state.overlay === "thread"
  const pinned = current?.pinned_at != null

  const closeMenu = React.useCallback(
    () => dispatch({ type: "overlay", overlay: null }),
    [dispatch],
  )

  // Opening another conversation abandons a rename left in flight. The field
  // stands in for the name of a Thread, and the Thread it was naming is gone.
  React.useEffect(() => setRenaming(false), [desk.threadId])

  const pin = React.useCallback(() => {
    if (current === undefined) return
    closeMenu()
    update.mutate({ threadId: current.id, pinned: !pinned })
  }, [closeMenu, current, pinned, update])

  const rename = React.useCallback(() => {
    if (current === undefined) return
    closeMenu()
    setRenaming(true)
  }, [closeMenu, current])

  const drop = React.useCallback(() => {
    if (current === undefined) return
    closeMenu()
    // The conversation on screen cannot survive its own Thread. This menu only
    // ever names the open one, so the empty composer is always where it lands.
    remove.mutate(current.id, { onSuccess: () => desk.newThread() })
  }, [closeMenu, current, desk, remove])

  // The letters printed down the right edge of the menu, made true. Bound only
  // while the menu is open, because a bare `d` that deletes a conversation from
  // anywhere would fire on the first word typed into the composer.
  React.useEffect(() => {
    if (!menuOpen) return
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const act = { p: pin, r: rename, d: drop }[event.key.toLowerCase()]
      if (act === undefined) return
      event.preventDefault()
      act()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [menuOpen, pin, rename, drop])

  return (
    <header className="flex flex-none items-center gap-2 px-5 py-3">
      {!state.sidebarOpen && <OpenSidebarButton onClick={() => dispatch({ type: "toggle-sidebar" })} />}

      {/* The desk does not repeat the conversation's name.
          On the desk this bar sits above a ~427px column, and the name is the
          one thing on it that is neither a control nor part of what the reader
          came to look at — the list already says which conversation is open,
          one corner away. The chevron goes with it rather than being left
          naming nothing: switching the desk off brings the title and the menu
          back together. */}
      {!state.signalDesk &&
        (renaming && current !== undefined ? (
          // The name, as a text field, in the place the name was. A dialog to
          // change one word would take the reader off the conversation they are
          // reading; the field commits and abandons by the same three keys the
          // sidebar's rename does, because it is the same field.
          <div className="min-w-0 max-w-[26rem] flex-1">
            <RenameField
              row={current}
              onDone={(next) => {
                setRenaming(false)
                if (next !== null && next !== (current.title ?? "")) {
                  update.mutate({ threadId: current.id, title: next })
                }
              }}
            />
          </div>
        ) : (
          <div className="relative flex min-w-0 items-center gap-1">
            <h1
              title={title === fullTitle ? undefined : fullTitle}
              className="min-w-0 truncate text-[0.95rem] font-normal text-ink-2"
            >
              {title}
            </h1>
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

            {/* The same 212px the sidebar's per-Thread menu is: it is the same
                menu over the same four writes, and two widths for one object
                read as two different menus. Fixed rather than grown to fit, so
                the box does not change shape when Ghim becomes Bỏ ghim. */}
            {menuOpen && (
              <Menu className="absolute left-0 top-[34px] w-[212px] rounded-xl">
                {/* Every row is dead while the bar names a conversation that
                    does not exist yet — there is nothing on the server to pin,
                    rename or delete until the first question opens one. */}
                <MenuItem
                  icon={
                    pinned ? (
                      <PinOff className="size-4 text-ink-4" strokeWidth={1.6} />
                    ) : (
                      <Pin className="size-4 text-ink-4" strokeWidth={1.6} />
                    )
                  }
                  hint="P"
                  disabled={current === undefined}
                  onClick={pin}
                >
                  {pinned ? "Bỏ ghim" : "Ghim"}
                </MenuItem>
                {/* Read state is not a thing a Thread has: the API carries no
                    such field, so there is nothing to write and nothing for the
                    list to draw differently. Left as the shape of the row it
                    will be, badged as unavailable rather than wired to a value
                    this browser would be the only holder of. */}
                <MenuItem icon={<EyeOff className="size-4 text-ink-4" strokeWidth={1.6} />} hint="U" disabled quiet>
                  Đánh dấu chưa đọc
                </MenuItem>
                <MenuItem
                  icon={<Pencil className="size-4 text-ink-4" strokeWidth={1.6} />}
                  hint="R"
                  disabled={current === undefined}
                  onClick={rename}
                >
                  Đổi tên
                </MenuItem>
                <MenuSeparator />
                <MenuItem
                  icon={<Trash2 className="size-4" strokeWidth={1.6} />}
                  hint="D"
                  destructive
                  disabled={current === undefined}
                  onClick={drop}
                >
                  Xoá
                </MenuItem>
              </Menu>
            )}
          </div>
        ))}

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

/** Words kept from a conversation's name in the bar above it. */
const TITLE_WORDS = 6

/**
 * The name of a conversation, cut to the first few words.
 *
 * A Thread is named after the sentence that opened it, so the name is a whole
 * question and the bar is wide enough to print most of one. `truncate` alone
 * cuts wherever the column happens to end, which makes the same conversation
 * read differently at two window widths. Cutting by words instead gives the
 * row a length of its own; the CSS clip stays as the second gate for a name
 * with no spaces in it. The full name rides along as the tooltip.
 */
function shorten(name: string): string {
  const words = name.split(/\s+/).filter(Boolean)
  if (words.length <= TITLE_WORDS) return name
  return `${words.slice(0, TITLE_WORDS).join(" ")}…`
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
