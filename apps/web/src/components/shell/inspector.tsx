"use client"

/**
 * The right-hand panel — post-rip-out, and now with two things in it.
 *
 * The market lenses (indices, VN30 overview, sector performance, stock detail
 * cards, price history, news sources) that used to live here were removed with
 * the market surfaces on 2026-08-25. What a chat lane needs is what is left:
 * the citations behind the answer in view, and the picture the answer was
 * written about.
 *
 * They are two tabs of one panel rather than two panels, because they answer
 * the same question from two sides — *what is this answer resting on* — and a
 * reader comparing a figure with its source should not have to choose which
 * half of the screen to give up.
 */

import dynamic from "next/dynamic"
import { X } from "lucide-react"

import { cn } from "@/lib/utils"

import { IconButton } from "./primitives"
import { maxInspectorWidth, useInspectorDrag, useShell } from "./shell-state"
import { SourcesTab } from "./sources-tab"

/**
 * The canvas panel arrives with the chart runtime behind it.
 *
 * Loaded on demand rather than with the shell: recharts is the largest thing in
 * this application by some way, and most conversations never draw anything. A
 * reader who asks a question that does produce a picture is already waiting on
 * a model call, which is the moment there is room to fetch a chart library.
 */
const CanvasPanel = dynamic(
  () => import("@/components/canvas/canvas-panel").then((m) => m.CanvasPanel),
  {
    ssr: false,
    loading: () => (
      <div
        aria-hidden
        className="m-3 h-32 animate-pulse rounded-lg border border-hairline bg-surface-sunken"
      />
    ),
  },
)

const TABS = [
  { id: "sources", label: "Nguồn" },
  { id: "canvas", label: "Phân tích" },
] as const

export function Inspector() {
  const { state, dispatch, panelWidth } = useShell()
  const onDrag = useInspectorDrag()

  const compact = state.viewport > 0 && state.viewport < 768
  const open = panelWidth > 0
  // Anything that is not the canvas is the sources tab: the four market lenses
  // are gone, and a tab id left over from one of them must still draw something.
  const active = state.inspector === "canvas" ? "canvas" : "sources"

  if (!open) return null

  return (
    <aside
      role="complementary"
      aria-label="Chat inspector"
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
        aria-label="Resize inspector panel"
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

      <header className="flex items-center justify-between border-b border-border pl-2 pr-4">
        <div role="tablist" aria-label="Inspector" className="flex">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active === tab.id}
              onClick={() => dispatch({ type: "open-inspector", tab: tab.id })}
              className={cn(
                "border-b-2 px-3 py-2.5 text-sm transition-colors",
                active === tab.id
                  ? "border-primary font-medium text-ink-1"
                  : "border-transparent text-muted-foreground hover:text-ink-2",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <IconButton
          label="Close inspector"
          onClick={() => dispatch({ type: "close-inspector" })}
        >
          <X className="size-4" />
        </IconButton>
      </header>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {active === "canvas" ? (
          <CanvasPanel
            artifactId={state.canvasArtifactId}
            // Frozen while the handle is held: a chart that re-measures on
            // every pointer move makes the drag stutter, and the numbers have
            // not changed while the reader is resizing the panel.
            frozen={state.dragging}
          />
        ) : (
          <SourcesTab />
        )}
      </div>
    </aside>
  )
}
