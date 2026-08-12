"use client"

/**
 * PROTOTYPE — throwaway. Issue #21.
 *
 * The mechanics of "an artifact inline in a thread that can expand to full
 * width", shared by every variant. Only the mechanics: what the expanded panel
 * *contains* is each variant's own answer, which is the thing under test.
 */

import * as React from "react"
import { Maximize2, X } from "lucide-react"

export function useExpanded() {
  const [expanded, setExpanded] = React.useState(false)

  React.useEffect(() => {
    if (!expanded) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [expanded])

  return { expanded, setExpanded }
}

export function ExpandButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
    >
      <Maximize2 className="h-3 w-3" />
      Mở rộng
    </button>
  )
}

/** Sits below the app header (h-16) so the real chrome stays visible. */
export function ExpandOverlay({
  onClose,
  children,
}: {
  onClose: () => void
  children: React.ReactNode
}) {
  return (
    <div className="fixed inset-x-0 bottom-0 top-16 z-30 bg-background/80 backdrop-blur-sm">
      <div className="mx-auto flex h-full w-full max-w-[92rem] flex-col p-4">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-xl">
          <div className="flex shrink-0 items-center justify-end border-b border-border px-3 py-2">
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <X className="h-3 w-3" />
              Thu gọn (Esc)
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">{children}</div>
        </div>
      </div>
    </div>
  )
}
