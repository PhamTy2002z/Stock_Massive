"use client"

import { X } from "lucide-react"

import { cn } from "@/lib/utils"

import { IconButton } from "./primitives"
import { maxInspectorWidth, useInspectorDrag, useShell } from "./shell-state"
import { SourcesTab } from "./sources-tab"

/**
 * The right-hand panel — post-rip-out.
 *
 * The market lenses (indices, VN30 overview, sector performance, stock detail
 * cards, price history, news sources) that used to live here were removed
 * with the market surfaces on 2026-08-25. What stays is the source panel: the
 * transcript's citations for the answer currently in view. That is the one
 * inspector surface a chat lane needs.
 */
export function Inspector() {
  const { state, dispatch, panelWidth } = useShell()
  const onDrag = useInspectorDrag()

  const compact = state.viewport > 0 && state.viewport < 768
  const open = panelWidth > 0

  if (!open) return null

  return (
    <aside
      role="complementary"
      aria-label="Chat sources"
      style={{ width: compact ? "100%" : panelWidth }}
      className={cn(
        "fixed right-0 top-0 z-20 flex h-dvh flex-col border-l border-border bg-background/95 backdrop-blur",
        compact ? "shadow-2xl" : "",
      )}
    >
      <div
        role="separator"
        tabIndex={0}
        aria-orientation="vertical"
        aria-label="Resize sources panel"
        aria-valuemin={0}
        aria-valuemax={maxInspectorWidth(state.viewport)}
        aria-valuenow={panelWidth}
        onPointerDown={onDrag}
        onKeyDown={(event) => {
          let width = panelWidth
          const step = event.shiftKey ? 40 : 12
          if (event.key === "ArrowLeft") width = panelWidth + step
          if (event.key === "ArrowRight") width = panelWidth - step
          if (event.key === "Home") width = 0
          if (event.key === "End") width = maxInspectorWidth(state.viewport)
          if (width !== panelWidth) {
            event.preventDefault()
            dispatch({ type: "resize-inspector", width })
          }
        }}
        className="absolute left-0 top-0 h-full w-1 cursor-col-resize bg-transparent hover:bg-border/60"
      />

      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-sm font-medium">Sources</span>
        <IconButton
          label="Close sources"
          onClick={() => dispatch({ type: "close-inspector" })}
        >
          <X className="size-4" />
        </IconButton>
      </header>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        <SourcesTab />
      </div>
    </aside>
  )
}
