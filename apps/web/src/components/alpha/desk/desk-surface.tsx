"use client"

import { AlertCircle, X } from "lucide-react"

import type { TranscriptEntry } from "@/lib/alpha-desk/transcript"
import type { FlagReason } from "@/lib/alpha-desk/types"
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
  opening,
  entries,
  activeSymbol,
  canCancel,
  isCancelling,
  isSubmitting,
  refusal,
  onSend,
  onCancel,
  onRetry,
  onFlag,
  onUnflag,
  flagFailedFor,
  onDismissRefusal,
  className,
}: {
  /** The Watchlist dock. Rendered by the container, which owns the rail query. */
  dock: React.ReactNode
  /** History / Related Analysis, as a compact surface. Never a second rail. */
  history?: React.ReactNode
  /** The first-run screen, assembled by the container so it can be live. */
  opening?: React.ReactNode
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
  /** The one dispute action v1 ships. Optional: without it, no control is drawn. */
  onFlag?: (messageId: number, reason: FlagReason) => void
  onUnflag?: (messageId: number) => void
  /**
   * The message whose last flag write was rejected.
   *
   * Beside the transcript rather than in the refusal strip below it: an
   * admission refusal is about the Turn the user is waiting on, and a flag that
   * did not save is about one answer they had already finished reading.
   */
  flagFailedFor?: number | null
  onDismissRefusal: () => void
  className?: string
}) {
  return (
    <div className={cn("flex h-full min-h-0 w-full flex-col overflow-hidden", className)}>
      {dock}

      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-4 py-2 text-meta">
        <p className="min-w-0 truncate text-muted-foreground">
          {activeSymbol ? (
            <>
              {/* The lens is named because "this symbol" has to mean something
                  the user can see. It organises the Analysis context and
                  nothing else — the Thread stays free-roaming. */}
              <span className="hidden sm:inline">Đang xem: </span>
              <span className="font-mono font-medium text-foreground">{activeSymbol}</span>
            </>
          ) : (
            <span className="hidden sm:inline">Chưa chọn mã nào làm ngữ cảnh</span>
          )}
        </p>
        <div className="flex shrink-0 items-center gap-1">{history}</div>
      </div>

      {/* Before the first question the whole cluster — greeting, opening copy
          and the field — sits in the middle of the surface, the way the
          reference opens a new conversation. Afterwards the transcript takes
          the height and the composer returns to the floor.

          The composer stays in the same place in the tree through that change,
          and only its container's justification moves: remounting it would
          drop focus and discard what was half-typed at the exact moment the
          conversation starts. */}
      <div
        className={cn(
          "flex min-h-0 flex-1 flex-col",
          entries.length === 0 && "justify-center"
        )}
      >
        <Transcript
          entries={entries}
          opening={opening}
          onRetry={onRetry}
          onFlag={onFlag}
          onUnflag={onUnflag}
          flagFailedFor={flagFailedFor}
          className={cn(entries.length === 0 ? "shrink-0" : "min-h-0 flex-1")}
        />

        {refusal && (
          <div
            role="alert"
            className="flex shrink-0 items-start gap-2 border-t border-destructive/40 bg-destructive/[0.07] px-4 py-2.5 text-meta text-destructive"
          >
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <p className="min-w-0 flex-1">{refusal}</p>
            <button
              type="button"
              onClick={onDismissRefusal}
              aria-label="Dismiss"
              className="shrink-0 rounded-md p-0.5 transition-colors hover:bg-destructive/15"
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
    </div>
  )
}
