"use client"

import { CAPTURE_COPY } from "@/lib/alpha-desk/copy"

import { useDesk } from "./desk-state"

/**
 * The frame that was captured, before anything is sent.
 *
 * This step is the whole reason the capture flow is three presses instead of
 * one. `getDisplayMedia` returns everything the reader agreed to share, which
 * may be a whole screen holding a tab, a message, an inbox — and once it has
 * gone to a model it cannot be taken back. So the picture is put in front of
 * them at full width with two plain choices, and neither is preselected as the
 * safe one by being the only one drawn.
 *
 * If this phase ever has to be cut, cut the whole phase. Do not cut this step.
 */
export function CapturePreview() {
  const desk = useDesk()
  if (desk.capture === null) return null

  return (
    <div
      // The scrim dismisses on its own click; this must not.
      onClick={(event) => event.stopPropagation()}
      className="flex max-h-full w-full max-w-[720px] flex-col gap-3 overflow-hidden rounded-2xl border border-border bg-surface-sunken p-4 shadow-composer"
    >
      <p className="text-meta text-ink-3">{CAPTURE_COPY.explain}</p>
      <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-border bg-surface-bubble">
        {/* Not `next/image`: the source is a `blob:` URL for a frame drawn a
            moment ago, and the optimizer cannot fetch one. */}
        <img
          src={desk.capture.previewUrl}
          alt={CAPTURE_COPY.title}
          className="block h-auto w-full"
        />
      </div>
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={desk.discardCapture}
          className="inline-flex h-9 items-center rounded-[10px] border border-border px-3.5 text-control text-ink-3 transition-colors hover:bg-foreground/[0.06] hover:text-foreground"
        >
          {CAPTURE_COPY.discard}
        </button>
        <button
          type="button"
          onClick={desk.acceptCapture}
          className="inline-flex h-9 items-center rounded-[10px] bg-foreground px-3.5 text-control text-background transition-opacity hover:opacity-90"
        >
          {CAPTURE_COPY.accept}
        </button>
      </div>
    </div>
  )
}
