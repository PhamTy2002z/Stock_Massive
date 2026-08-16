"use client"

import { cn } from "@/lib/utils"

import { DeskProvider, useDesk } from "./desk-state"
import { Inspector } from "./inspector"
import { Overlays } from "./overlays"
import { ShellProvider, useShell } from "./shell-state"
import { Sidebar } from "./sidebar"
import { TopBar } from "./top-bar"
import { BoardView } from "./view-board"
import { ChatView } from "./view-chat"
import { NewConversationView } from "./view-new"

/**
 * VisgniteAI, whole.
 *
 * Three regions on one viewport: what you keep on the left, what you are doing
 * in the middle, and what the market is doing on the right. None of them is a
 * route — the reference is a single surface, and turning the views into pages
 * would throw away a half-typed question every time somebody looked at a price.
 *
 * The page itself never scrolls. Each region owns its own overflow, which is
 * what keeps the composer on the floor and the sidebar where it was left while
 * an answer several screens long arrives in between them.
 */
export function AppShell() {
  return (
    <ShellProvider>
      <DeskProvider>
        <Frame />
      </DeskProvider>
    </ShellProvider>
  )
}

function Frame() {
  const { state, dispatch, panelWidth } = useShell()

  return (
    <div className="relative flex h-dvh overflow-hidden bg-background text-foreground">
      {/* One transparent catcher for every open popover. Cheaper and more
          reliable than a listener per menu: the menus stop propagation on their
          own surface, so anything reaching this is genuinely "somewhere else". */}
      {(state.overlay === "account" ||
        state.overlay === "attach" ||
        state.overlay === "thread") && (
        <div
          className="fixed inset-0 z-[25]"
          onClick={() => dispatch({ type: "overlay", overlay: null })}
        />
      )}

      <Sidebar />

      <main
        style={{ paddingRight: panelWidth }}
        className={cn(
          "relative flex min-w-0 flex-1 flex-col",
          state.dragging
            ? "transition-none"
            : "transition-[padding] duration-panel ease-panel",
        )}
      >
        <TopBar />

        <MainView />
      </main>

      <Inspector />

      <Overlays />
    </div>
  )
}

/**
 * Which of the three screens the main column is showing.
 *
 * A conversation with nothing in it *is* the opening screen — they are not two
 * states the user chooses between, which is why this is derived from the
 * transcript rather than stored. Deriving it is also what makes the transition
 * free: the composer stays mounted across it and keeps focus and draft.
 */
function MainView() {
  const { state } = useShell()
  const desk = useDesk()

  if (state.view === "board") return <BoardView />
  if (state.view === "new" || desk.entries.length === 0) return <NewConversationView />
  return <ChatView />
}
