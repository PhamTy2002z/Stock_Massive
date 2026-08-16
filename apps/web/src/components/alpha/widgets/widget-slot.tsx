"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { lookupWidget } from "./registry"
import { parseWidgetSpec } from "./spec"
import type { WidgetData, WidgetSpec } from "./types"

/**
 * The position a Widget occupies in a transcript, from the moment text lands.
 *
 * **Text streams first.** A `content.block` is released as soon as it is proven
 * and a `widget.ready` arrives afterwards, so the slot exists before its data
 * does. It reserves its own height from the first render, which is why the
 * transcript does not jump when the picture finally arrives — a reader
 * mid-sentence is not scrolled away from it by a chart loading underneath.
 *
 * **Validation happens before lookup.** The persisted spec is re-parsed here,
 * ahead of asking the registry for anything, so an unknown `(name, version)`, a
 * malformed spec, or a component this build no longer ships is a miss rather
 * than a throw. Nothing in this file can take the text answer down with it.
 *
 * **Failure is asymmetric.** A Widget the agent offered disappears without
 * noise when it fails — the reader did not ask for it, and a broken box teaches
 * them nothing. One the user asked for leaves a short unavailable state with
 * Retry, because a question deserves an answer even when the answer is "not
 * right now". The bit that decides which is on the spec, put there by the
 * backend from the user's own words.
 */

export type SlotState = "loading" | "ready" | "failed" | "missing"

export interface WidgetSlotProps {
  /** The spec straight off the message, unvalidated on purpose. */
  spec: unknown
  /** Resolves a descriptor to its fixed slice. Injected, never imported. */
  resolve: (spec: WidgetSpec) => Promise<WidgetData>
  /** Opens the expanded view over the same fixed data. */
  onExpand?: (spec: WidgetSpec, data: WidgetData) => void
  className?: string
}

/** Tall enough to hold any of the four, so the swap moves nothing. */
export const PLACEHOLDER_CLASS = "h-[168px] w-full rounded-[18px] border border-border"

export function WidgetSlot({ spec, resolve, onExpand, className }: WidgetSlotProps) {
  // Parsed once per spec identity rather than on every render: the result is
  // what every branch below keys off, and re-deriving it would let a re-render
  // change which branch we are in.
  const parsed = React.useMemo(() => parseWidgetSpec(spec), [spec])
  const entry = parsed ? lookupWidget(parsed) : undefined

  const [attempt, setAttempt] = React.useState(0)
  const [state, setState] = React.useState<SlotState>(
    parsed && entry ? "loading" : "missing"
  )
  const [data, setData] = React.useState<WidgetData | null>(null)

  React.useEffect(() => {
    if (!parsed || !entry) {
      setState("missing")
      return
    }
    let live = true
    setState("loading")
    resolve(parsed)
      .then((resolved) => {
        if (!live) return
        // The registry's own pairing check. A descriptor kind that does not
        // match the component's is a spec and a build that disagree, and
        // rendering it anyway is how a ranking ends up drawn as a line.
        if (resolved.kind !== entry.kind) {
          setState("failed")
          return
        }
        setData(resolved)
        setState("ready")
      })
      .catch(() => {
        if (live) setState("failed")
      })
    return () => {
      live = false
    }
  }, [parsed, entry, resolve, attempt])

  // An unknown Widget leaves the text answer alone and says nothing. This is
  // the degradation ADR-0012 asks for, and it is one return statement.
  if (!parsed || !entry) return null

  if (state === "loading") {
    return (
      <div
        data-testid="widget-placeholder"
        aria-hidden="true"
        className={cn(
          PLACEHOLDER_CLASS,
          "bg-card motion-safe:animate-pulse motion-reduce:animate-none",
          className
        )}
      />
    )
  }

  if (state === "failed" || !data) {
    if (!parsed.requested) return null
    return (
      <div
        role="status"
        className={cn(
          "rounded-[18px] border border-border bg-card p-4 text-[13px]",
          className
        )}
      >
        <p>Không hiển thị được biểu đồ này.</p>
        <button
          type="button"
          onClick={() => setAttempt((count) => count + 1)}
          className="mt-2 rounded-md underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Thử lại
        </button>
      </div>
    )
  }

  const Component = entry.component
  return (
    <div className={cn("min-w-0", className)}>
      <Component
        spec={parsed}
        data={data}
        onExpand={onExpand ? () => onExpand(parsed, data) : undefined}
      />
    </div>
  )
}
