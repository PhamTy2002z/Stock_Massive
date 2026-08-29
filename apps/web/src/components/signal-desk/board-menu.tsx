"use client";

/**
 * The dropdown under the header's own control.
 *
 * The header names one board and the switcher holds a search box; this is the
 * step between them — every board of the conversation, one click away, without
 * the scrim and the typing. Pinned boards first in pin order, then the rest
 * newest first, because "the one I just made" and "the one I keep" are the two
 * boards a reader reaches for without searching.
 *
 * A row shows a title, a ticker and the analysis's Vietnamese name — never the
 * id it opens by, never the recipe's slug. The pin control is a sibling of the
 * row rather than a child, for the reason every second action on a row is: a
 * button inside a button is not something a browser lays out.
 */

import { useEffect, useRef } from "react";
import { Pin, PinOff, Search } from "lucide-react";

import { Menu, MenuItem, MenuSeparator } from "@/components/shell/primitives";
import type { SignalDeskBoard } from "@/components/shell/shell-state";
import { BOARD_SWITCHER_COPY } from "@/lib/alpha-desk/copy";
import { cn } from "@/lib/utils";

export interface BoardMenuProps {
  /** Every board in the conversation, oldest first. */
  boards: SignalDeskBoard[];
  /** The pinned ids, in pin order. */
  pinned: string[];
  activeBoardId: string | null;
  onOpenBoard: (artifactId: string) => void;
  onTogglePin: (artifactId: string, pinned: boolean) => void;
  /** Opens the searchable switcher, for a conversation too long to scan. */
  onSearch: () => void;
  onClose: () => void;
}

export function BoardMenu({
  boards,
  pinned,
  activeBoardId,
  onOpenBoard,
  onTogglePin,
  onSearch,
  onClose,
}: BoardMenuProps) {
  // The shell's scrim sits above the desk pane, so a menu drawn inside the pane
  // would be under it and every press would land on the scrim. This menu
  // therefore closes itself: a press anywhere outside it, or outside the control
  // that opened it, is a dismissal. Escape is the shell's, like every overlay.
  const surface = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      const root = surface.current?.parentElement;
      if (root !== null && root !== undefined && root.contains(target)) return;
      onClose();
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [onClose]);

  const byId = new Map(boards.map((board) => [board.artifactId, board]));
  const pinnedBoards = pinned.flatMap((id) => {
    const board = byId.get(id);
    return board === undefined ? [] : [board];
  });
  const others = [...boards]
    .filter((board) => !pinned.includes(board.artifactId))
    .reverse();

  const open = (artifactId: string) => {
    onOpenBoard(artifactId);
    onClose();
  };

  return (
    <div ref={surface} className="absolute left-0 top-full z-30 mt-1">
      <Menu className="w-[320px] max-w-[calc(100vw-1.5rem)]">
        <div className="max-h-[min(60vh,420px)] overflow-y-auto scrollbar-thin">
          {boards.length === 0 && (
            <p className="px-2.5 py-2 text-meta text-muted-foreground">
              {BOARD_SWITCHER_COPY.empty}
            </p>
          )}
          {pinnedBoards.length > 0 && (
            <Group label={BOARD_SWITCHER_COPY.pinnedGroup}>
              {pinnedBoards.map((board) => (
                <Row
                  key={board.artifactId}
                  board={board}
                  pinned
                  active={board.artifactId === activeBoardId}
                  onOpen={() => open(board.artifactId)}
                  onTogglePin={() => onTogglePin(board.artifactId, false)}
                />
              ))}
            </Group>
          )}
          {others.length > 0 && (
            <Group
              label={
                pinnedBoards.length > 0
                  ? BOARD_SWITCHER_COPY.othersGroup
                  : BOARD_SWITCHER_COPY.recentGroup
              }
            >
              {others.map((board) => (
                <Row
                  key={board.artifactId}
                  board={board}
                  pinned={false}
                  active={board.artifactId === activeBoardId}
                  onOpen={() => open(board.artifactId)}
                  onTogglePin={() => onTogglePin(board.artifactId, true)}
                />
              ))}
            </Group>
          )}
        </div>
        {boards.length > 0 && (
          <>
            <MenuSeparator />
            <MenuItem
              icon={<Search className="size-[15px] text-ink-4" aria-hidden />}
              hint={BOARD_SWITCHER_COPY.shortcut}
              onClick={() => {
                onClose();
                onSearch();
              }}
            >
              {BOARD_SWITCHER_COPY.search}
            </MenuItem>
          </>
        )}
      </Menu>
    </div>
  );
}

function Group({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div role="group" aria-label={label}>
      <p className="px-2.5 pb-1 pt-2 text-micro font-medium uppercase tracking-[0.06em] text-ink-6">
        {label}
      </p>
      {children}
    </div>
  );
}

function Row({
  board,
  pinned,
  active,
  onOpen,
  onTogglePin,
}: {
  board: SignalDeskBoard;
  pinned: boolean;
  active: boolean;
  onOpen: () => void;
  onTogglePin: () => void;
}) {
  const detail = [board.symbol, board.studyDisplayName]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="relative">
      <button
        type="button"
        role="menuitem"
        aria-current={active || undefined}
        onClick={onOpen}
        className={cn(
          "flex w-full flex-col items-start gap-0.5 rounded-[9px] py-1.5 pl-2.5 pr-9 text-left transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          active
            ? "bg-foreground/[0.08] text-ink-1"
            : "text-ink-2 hover:bg-foreground/[0.06]",
        )}
      >
        <span className="w-full truncate text-row">{board.title}</span>
        {detail !== "" && (
          <span className="w-full truncate text-micro text-ink-5">
            {detail}
          </span>
        )}
      </button>
      <button
        type="button"
        aria-label={
          pinned ? BOARD_SWITCHER_COPY.unpin : BOARD_SWITCHER_COPY.pin
        }
        title={pinned ? BOARD_SWITCHER_COPY.unpin : BOARD_SWITCHER_COPY.pin}
        onClick={onTogglePin}
        className="absolute right-1.5 top-1/2 flex size-6 -translate-y-1/2 items-center justify-center rounded text-ink-6 transition-colors hover:bg-foreground/10 hover:text-ink-2"
      >
        {pinned ? (
          <PinOff className="size-3.5" strokeWidth={1.8} aria-hidden />
        ) : (
          <Pin className="size-3.5" strokeWidth={1.8} aria-hidden />
        )}
      </button>
    </div>
  );
}
