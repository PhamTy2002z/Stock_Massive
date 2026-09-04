"use client"

/**
 * Every board this conversation drew, searchable, in one list.
 *
 * The header's dropdown scans; this searches. A working conversation makes
 * twenty boards and the sixteenth is past the end of anything a reader scans,
 * so this has to be a *good* way back rather than an overflow menu: a reader
 * hunting for "the liquidity one for STB" is remembering a ticker and a kind of
 * analysis, not a position in a list.
 *
 * So it searches three things at once — the board's title, the ticker it is
 * about, and the Vietnamese name of the analysis that drew it — and it searches
 * them without diacritics, because a reader typing fast types `thanh khoan`.
 *
 * **It shows nothing from the machinery.** Not the id it opens by, not the slug
 * the server keys the recipe under. Those are matched against, because a reader
 * who has seen a slug in an export should be able to paste it; they are never
 * printed. A row is a sentence a person wrote plus a ticker.
 *
 * Not virtualised on purpose. The list is bounded by one conversation's Turns
 * and a few hundred rows render in one frame — a windowing library here would
 * be a dependency and a scroll-restoration bug bought against a cost nobody has
 * measured.
 */

import { useEffect, useMemo, useRef, useState } from "react"
import { LayoutGrid, ListTree, Pin, PinOff, Search, X } from "lucide-react"

import type { SignalDeskBoard } from "@/components/shell/shell-state"
import { BOARD_SWITCHER_COPY } from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"

/** One thing the reader can press: a board, or the row that widens the list. */
type Row =
  | { kind: "board"; key: string; board: SignalDeskBoard; pinned: boolean; group: string }
  | { kind: "all"; key: string; group: string }

export interface BoardSwitcherProps {
  /** Every board in the conversation, oldest first. */
  boards: SignalDeskBoard[]
  /** The pinned ids, in pin order. */
  pinned: string[]
  activeBoardId: string | null
  onOpenBoard: (artifactId: string) => void
  onTogglePin: (artifactId: string, pinned: boolean) => void
  onClose: () => void
}

export function BoardSwitcher({
  boards,
  pinned,
  activeBoardId,
  onOpenBoard,
  onTogglePin,
  onClose,
}: BoardSwitcherProps) {
  const [term, setTerm] = useState("")
  // Whether the reader has asked for the whole conversation rather than the
  // handful they were last looking at. `*` is the same request typed.
  const [showAll, setShowAll] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const list = useRef<HTMLDivElement>(null)

  const query = normalise(term)
  const everything = showAll || term.trim() === "*"

  const rows = useMemo(
    () => buildRows({ boards, pinned, query, everything }),
    [boards, pinned, query, everything],
  )

  // A list that changed under the cursor must not leave the cursor past its
  // end: the next Enter would then open nothing and read as a dead keyboard.
  useEffect(() => setHighlight(0), [term, everything])

  useEffect(() => {
    const node = list.current?.querySelector<HTMLElement>('[data-highlighted="true"]')
    // Feature-detected rather than assumed: scrolling an element into view is
    // an optional part of the DOM, and a cursor that cannot be scrolled to is
    // still a cursor. Throwing here would take the whole list down.
    if (typeof node?.scrollIntoView === "function") node.scrollIntoView({ block: "nearest" })
  }, [highlight, rows])

  function activate(row: Row | undefined): void {
    if (row === undefined) return
    if (row.kind === "all") {
      setShowAll(true)
      return
    }
    onOpenBoard(row.board.artifactId)
    onClose()
  }

  function onKeyDown(event: React.KeyboardEvent): void {
    if (event.key === "ArrowDown") {
      event.preventDefault()
      setHighlight((at) => (rows.length === 0 ? 0 : (at + 1) % rows.length))
      return
    }
    if (event.key === "ArrowUp") {
      event.preventDefault()
      setHighlight((at) => (rows.length === 0 ? 0 : (at - 1 + rows.length) % rows.length))
      return
    }
    if (event.key === "Enter") {
      event.preventDefault()
      activate(rows[highlight])
    }
  }

  return (
    <div
      onClick={(event) => event.stopPropagation()}
      onKeyDown={onKeyDown}
      className="w-full max-w-[620px] animate-vg-message-in overflow-hidden rounded-2xl border border-border bg-surface-sunken shadow-modal"
    >
      <div className="flex items-center gap-2.5 border-b border-border px-4 py-3.5">
        <Search className="size-[18px] shrink-0 text-ink-5" strokeWidth={1.6} aria-hidden />
        <input
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          autoFocus
          role="combobox"
          aria-expanded
          aria-controls="board-switcher-list"
          aria-label={BOARD_SWITCHER_COPY.title}
          placeholder={BOARD_SWITCHER_COPY.placeholder}
          className="min-w-0 flex-1 border-0 bg-transparent text-row text-foreground outline-none placeholder:text-ink-6"
        />
        <button
          type="button"
          title={BOARD_SWITCHER_COPY.open}
          aria-label={BOARD_SWITCHER_COPY.open}
          aria-pressed={everything}
          onClick={() => setShowAll(true)}
          className={cn(
            "flex size-7 shrink-0 items-center justify-center rounded-lg transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            everything ? "bg-foreground/[0.08] text-foreground" : "text-ink-5 hover:text-ink-2",
          )}
        >
          <ListTree className="size-4" strokeWidth={1.7} aria-hidden />
        </button>
        <button
          type="button"
          title="Đóng"
          aria-label="Đóng"
          onClick={onClose}
          className="flex size-7 shrink-0 items-center justify-center rounded-lg text-ink-5 transition-colors hover:bg-foreground/[0.06] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="size-3.5" strokeWidth={1.8} aria-hidden />
        </button>
      </div>

      <div
        ref={list}
        id="board-switcher-list"
        role="listbox"
        aria-label={BOARD_SWITCHER_COPY.title}
        className="scrollbar-thin max-h-[52vh] overflow-y-auto p-1.5"
      >
        {rows.map((row, at) => {
          const heading = row.group !== rows[at - 1]?.group ? row.group : null
          return (
            <div key={row.key}>
              {heading !== null && (
                <p className="px-2.5 pb-1 pt-2.5 text-eyebrow font-semibold uppercase tracking-[0.06em] text-ink-6">
                  {heading}
                </p>
              )}
              {row.kind === "all" ? (
                <button
                  type="button"
                  role="option"
                  aria-selected={at === highlight}
                  data-highlighted={at === highlight}
                  onMouseEnter={() => setHighlight(at)}
                  onClick={() => activate(row)}
                  className={cn(ROW, at === highlight && ROW_ON)}
                >
                  <LayoutGrid className="size-[17px] shrink-0 text-ink-5" strokeWidth={1.5} aria-hidden />
                  <span className="min-w-0 flex-1 truncate text-ink-3">
                    {BOARD_SWITCHER_COPY.showAll}
                  </span>
                </button>
              ) : (
                <BoardRow
                  row={row}
                  highlighted={at === highlight}
                  active={row.board.artifactId === activeBoardId}
                  onHover={() => setHighlight(at)}
                  onOpen={() => activate(row)}
                  onTogglePin={() => onTogglePin(row.board.artifactId, !row.pinned)}
                />
              )}
            </div>
          )
        })}

        {rows.length === 0 && (
          <p className="px-2.5 py-6 text-center text-row text-ink-6">
            {boards.length === 0 ? BOARD_SWITCHER_COPY.empty : BOARD_SWITCHER_COPY.noMatch}
          </p>
        )}
      </div>
    </div>
  )
}

function BoardRow({
  row,
  highlighted,
  active,
  onHover,
  onOpen,
  onTogglePin,
}: {
  row: Extract<Row, { kind: "board" }>
  highlighted: boolean
  active: boolean
  onHover: () => void
  onOpen: () => void
  onTogglePin: () => void
}) {
  const { board, pinned } = row
  // The recipe's Vietnamese name, and nothing when there is not one. The slug
  // is matched against and never drawn: see the note at the top of the file.
  const analysis = board.studyName === undefined ? "" : (board.studyDisplayName ?? "")

  return (
    // A row rather than a button, because the pin is a second action on one
    // board: a button inside a button is not something a browser lays out.
    <div
      role="presentation"
      onMouseEnter={onHover}
      className={cn("relative", highlighted && "rounded-[9px] bg-surface-raised")}
    >
      <button
        type="button"
        role="option"
        aria-selected={highlighted}
        aria-current={active ? "true" : undefined}
        data-highlighted={highlighted}
        onClick={onOpen}
        className={cn(ROW, "pr-10")}
      >
        <LayoutGrid className="size-[17px] shrink-0 text-ink-5" strokeWidth={1.5} aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-foreground">{board.title}</span>
          {(board.symbol || analysis) && (
            <span className="mt-0.5 block truncate text-control text-ink-5">
              {[board.symbol, analysis].filter(Boolean).join(" · ")}
            </span>
          )}
        </span>
      </button>
      <button
        type="button"
        title={pinned ? BOARD_SWITCHER_COPY.unpin : BOARD_SWITCHER_COPY.pin}
        aria-label={pinned ? BOARD_SWITCHER_COPY.unpin : BOARD_SWITCHER_COPY.pin}
        aria-pressed={pinned}
        onClick={onTogglePin}
        className={cn(
          "absolute right-2 top-1/2 flex size-7 -translate-y-1/2 items-center justify-center rounded-lg transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          pinned ? "text-foreground" : "text-ink-6 hover:bg-foreground/10 hover:text-ink-2",
        )}
      >
        {pinned ? (
          <PinOff className="size-3.5" strokeWidth={1.7} aria-hidden />
        ) : (
          <Pin className="size-3.5" strokeWidth={1.7} aria-hidden />
        )}
      </button>
    </div>
  )
}

const ROW =
  "flex w-full items-center gap-2.5 rounded-[9px] px-2.5 py-2 text-left text-row transition-colors hover:bg-foreground/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
const ROW_ON = "bg-surface-raised"

/**
 * The rows the list shows, in the order it shows them.
 *
 * Three shapes out of one function, because they are three answers to the same
 * question and splitting them would let the grouping rules drift apart:
 *
 * - **nothing typed** — pinned, then newest first, then the row that regroups
 *   the list by the question each board answered;
 * - **something typed** — one flat group of matches, best-effort by relevance
 *   only in so far as pinned boards come first;
 * - **everything** — the whole conversation in the order it was drawn, grouped
 *   by the Turn that drew it, because "the third thing I asked" is how a reader
 *   remembers a board they cannot name.
 */
export function buildRows({
  boards,
  pinned,
  query,
  everything,
}: {
  boards: SignalDeskBoard[]
  pinned: string[]
  query: string
  everything: boolean
}): Row[] {
  const isPinned = (board: SignalDeskBoard) => pinned.includes(board.artifactId)
  const searching = query !== "" && query !== "*"
  const matching = searching ? boards.filter((board) => matches(board, query)) : boards

  if (everything) {
    return [...matching]
      .sort((left, right) => (left.round ?? 0) - (right.round ?? 0))
      .map((board) => ({
        kind: "board" as const,
        key: board.artifactId,
        board,
        pinned: isPinned(board),
        group: BOARD_SWITCHER_COPY.round(board.round ?? 0),
      }))
  }

  if (searching) {
    return matching
      .map((board) => ({
        kind: "board" as const,
        key: board.artifactId,
        board,
        pinned: isPinned(board),
        group: BOARD_SWITCHER_COPY.allGroup,
      }))
      .sort((left, right) => Number(right.pinned) - Number(left.pinned))
  }

  const rows: Row[] = []
  for (const artifactId of pinned) {
    const board = boards.find((one) => one.artifactId === artifactId)
    if (board === undefined) continue
    rows.push({
      kind: "board",
      key: board.artifactId,
      board,
      pinned: true,
      group: BOARD_SWITCHER_COPY.pinnedGroup,
    })
  }
  // Newest first, and the pinned ones are already above rather than twice.
  for (const board of [...boards].reverse()) {
    if (isPinned(board)) continue
    rows.push({
      kind: "board",
      key: board.artifactId,
      board,
      pinned: false,
      group: BOARD_SWITCHER_COPY.recentGroup,
    })
  }
  // Offered whenever there is something to regroup: the flat list above answers
  // "which one did I just make", and this one answers "which one came out of
  // the third thing I asked".
  if (boards.length > 0) {
    rows.push({ kind: "all", key: "__all__", group: BOARD_SWITCHER_COPY.allGroup })
  }
  return rows
}

/** Whether one board answers to what was typed. */
function matches(board: SignalDeskBoard, query: string): boolean {
  const haystack = [board.title, board.symbol, board.studyDisplayName, board.studyName]
    .filter((part): part is string => typeof part === "string" && part !== "")
    .map(normalise)
  return haystack.some((part) => part.includes(query))
}

/**
 * A string as a reader types it: lower case, unaccented, `đ` folded to `d`.
 *
 * Simple on purpose. This is a filter over at most a few hundred short strings
 * a person just read, not a search engine — Unicode decomposition strips the
 * combining marks Vietnamese stacks on its vowels, and `đ` is the one letter
 * that survives decomposition because its stroke is part of the glyph.
 */
export function normalise(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .trim()
}
