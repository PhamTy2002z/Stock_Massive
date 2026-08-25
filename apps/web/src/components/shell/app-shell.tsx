"use client"

import { cn } from "@/lib/utils"

import { DeskProvider } from "./desk-state"
import { Inspector } from "./inspector"
import { Overlays } from "./overlays"
import { ShellProvider, useShell } from "./shell-state"
import { Sidebar } from "./sidebar"
import { TopBar } from "./top-bar"
import { ChatView } from "./view-chat"

/**
 * VisgniteAI, whole.
 *
 * Three regions on one viewport: sidebar, chat column, inspector. The board,
 * news and new-conversation views were removed with the market surfaces
 * (2026-08-25). The main column now only ever renders the chat.
 *
 * The page itself never scrolls. Each region owns its own overflow.
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
        style={{ paddingRight: state.viewport > 0 && state.viewport < 768 ? 0 : panelWidth }}
        className={cn(
          "relative flex min-w-0 flex-1 flex-col",
          state.dragging
            ? "transition-none"
            : "transition-[padding] duration-panel ease-panel",
        )}
      >
        <TopBar />
        <ChatView />
      </main>

      <Inspector />

      <Overlays />
    </div>
  )
}
