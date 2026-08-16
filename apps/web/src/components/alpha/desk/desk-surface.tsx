"use client"

import { AlertCircle, X } from "lucide-react"

import type { TranscriptEntry } from "@/lib/alpha-desk/transcript"
import { cn } from "@/lib/utils"
import { Composer } from "./composer"
import { Transcript } from "./transcript"

/**
 * The Alpha Desk shell, with every decision already made.
 *
 * Presentational on purpose. The container above it owns the Thread, the live
 * Turn and the rail; this owns the box — a compact dock, a slim header, a
 * conversation that scrolls inside itself, and a composer pinned to the bottom.
 * Splitting them is what lets the layout claims be tested by rendering rather
 * than by mocking three query hooks to get at a `<div>`.
 *
 * **The shape survives a narrow viewport.** Every child that can grow is
 * `min-w-0`, the dock scrolls horizontally inside itself, and header actions
 * drop their labels rather than pushing the row wider — so the page body never
 * gains a horizontal scrollbar (`docs/specs/0002` §8).
 */
export function DeskSurface({
  dock,
  history,
  entries,
  activeSymbol,
  canCancel,
  isCancelling,
  isSubmitting,
  refusal,
  onSend,
  onCancel,
  onRetry,
  onDismissRefusal,
  className,
}: {
  /** The Watchlist dock. Rendered by the container, which owns the rail query. */
  dock: React.ReactNode
  /** History / Related Analysis, as a compact surface. Never a second rail. */
  history?: React.ReactNode
  entries: TranscriptEntry[]
  activeSymbol: string | null
  canCancel: boolean
  isCancelling: boolean
  isSubmitting: boolean
  /** An admission refusal, which is an HTTP outcome and never a stream event. */
  refusal: string | null
  onSend: (text: string) => void
  onCancel: () => void
  onRetry: () => void
  onDismissRefusal: () => void
  className?: string
}) {
  return (
    <div className={cn("flex h-full min-h-0 w-full flex-col overflow-hidden", className)}>
      {dock}

      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border/60 px-3 py-1.5 text-xs">
        <p className="min-w-0 truncate text-muted-foreground">
          {activeSymbol ? (
            <>
              {/* The lens is named because "this symbol" has to mean something
                  the user can see. It organises the Analysis context and
                  nothing else — the Thread stays free-roaming. */}
              <span className="hidden sm:inline">Đang xem: </span>
              <span className="font-medium text-foreground">{activeSymbol}</span>
            </>
          ) : (
            <span className="hidden sm:inline">Chưa chọn mã nào làm ngữ cảnh</span>
          )}
        </p>
        <div className="flex shrink-0 items-center gap-1">{history}</div>
      </div>

      <Transcript entries={entries} onRetry={onRetry} className="min-h-0 flex-1" />

      {refusal && (
        <div
          role="alert"
          className="flex shrink-0 items-start gap-2 border-t border-red-500/40 bg-red-500/5 px-3 py-2 text-xs text-red-600 dark:text-red-400"
        >
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <p className="min-w-0 flex-1">{refusal}</p>
          <button
            type="button"
            onClick={onDismissRefusal}
            aria-label="Dismiss"
            className="shrink-0 rounded p-0.5 hover:bg-red-500/10"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      <Composer
        onSend={onSend}
        onCancel={onCancel}
        canCancel={canCancel}
        isCancelling={isCancelling}
        isSubmitting={isSubmitting}
        activeSymbol={activeSymbol}
        className="shrink-0"
      />
    </div>
  )
}
