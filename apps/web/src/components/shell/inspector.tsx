"use client"

import { X } from "lucide-react"

import { useShell } from "./shell-state"
import { IconButton } from "./primitives"
import { SourcesTab } from "./sources-tab"

/** Narrow supporting drawer for the sources behind the active answer. */
export function Inspector() {
  const { state, dispatch, panelWidth } = useShell()
  if (state.inspector === null) return null

  return (
    <aside
      role="complementary"
      aria-label="Nguồn"
      style={{ width: state.viewport > 0 && state.viewport < 768 ? "100%" : panelWidth }}
      className="fixed right-0 top-0 z-20 flex h-dvh min-w-0 flex-col border-l border-border bg-background shadow-xl md:shadow-none"
    >
      <header className="flex flex-none items-center justify-between border-b border-border px-4 py-2.5">
        <h2 className="text-sm font-medium text-ink-1">Nguồn</h2>
        <IconButton
          label="Đóng nguồn"
          onClick={() => dispatch({ type: "close-inspector" })}
        >
          <X className="size-4" />
        </IconButton>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 scrollbar-thin">
        <SourcesTab />
      </div>
    </aside>
  )
}
