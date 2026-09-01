"use client"

import { useEffect } from "react"

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

  // The composer's menu dismisses itself rather than through the scrim below,
  // because the scrim would be *over* it.
  //
  // The scrim is a sibling of `main` carrying `z-[25]`, and `main` is
  // positioned with `z-index: auto`. A positioned ancestor with no z-index of
  // its own still paints as one unit, so nothing inside `main` can out-paint a
  // positive-z sibling of it — a menu drawn in the composer sits under the
  // scrim however high its own z-index goes, and every press on it lands on the
  // scrim instead. Measured: `elementsFromPoint` over a menu row returned the
  // scrim first, and raising the composer to `z-40` changed nothing.
  //
  // A press on the trigger is left alone — it is `aria-expanded` while the menu
  // is open, and closing here would let its own click reopen what it meant to
  // shut.
  useEffect(() => {
    if (state.overlay !== "attach") return
    function onPointerDown(event: PointerEvent) {
      const target = event.target
      const element =
        target instanceof Element
          ? target
          : target instanceof Node
            ? target.parentElement
            : null
      if (
        element?.closest(
          '[role="menu"], [aria-haspopup="menu"][aria-expanded="true"]',
        )
      ) {
        return
      }
      dispatch({ type: "overlay", overlay: null })
    }
    document.addEventListener("pointerdown", onPointerDown)
    return () => document.removeEventListener("pointerdown", onPointerDown)
  }, [state.overlay, dispatch])

  return (
    <div className="relative flex h-dvh overflow-hidden bg-background text-foreground">
      {(state.overlay === "account" || state.overlay === "thread") && (
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
