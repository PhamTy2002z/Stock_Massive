"use client"

import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"
import { lookupWidget } from "./registry"
import type { WidgetData, WidgetSpec } from "./types"
import { formatDataDate } from "./widget-frame"

/**
 * **Expand**: the same fixed data, full-screen, and nothing more.
 *
 * There is no chart editor in v1 and this is where that decision is visible —
 * the expanded view re-renders the *same* component from the *same* resolved
 * data, with its table already open. It re-resolves nothing, so it cannot show
 * a different slice from the one the reader was just looking at.
 *
 * **View calculation** is a disclosure rather than a panel, and it holds what
 * the answer itself deliberately keeps out of the prose: the field, the tool
 * calls it came from, and the date. Method names and identifiers belong under a
 * disclosure, not in a sentence a reader has to step over.
 *
 * Radix owns the focus trap, the Escape key and the `aria-modal` wiring. Doing
 * that by hand is the kind of code that is written once and then quietly stops
 * working the third time the markup moves.
 */
export interface WidgetExpandProps {
  spec: WidgetSpec | null
  data: WidgetData | null
  onOpenChange: (open: boolean) => void
}

export function WidgetExpand({ spec, data, onOpenChange }: WidgetExpandProps) {
  const entry = spec ? lookupWidget(spec) : undefined
  const open = Boolean(spec && data && entry)

  if (!spec || !data || !entry) return null
  const Component = entry.component

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/70" />
        <DialogPrimitive.Content className="fixed inset-0 z-50 overflow-y-auto bg-background p-4 sm:p-6">
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <DialogPrimitive.Title className="text-[17px] font-semibold leading-[1.24]">
                  {spec.title}
                </DialogPrimitive.Title>
                <DialogPrimitive.Description className="text-[13px] text-muted-foreground">
                  Dữ liệu ngày {formatDataDate(data.as_of)}
                </DialogPrimitive.Description>
              </div>
              <DialogPrimitive.Close
                aria-label="Đóng"
                className="rounded-md p-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X className="size-4" />
              </DialogPrimitive.Close>
            </div>

            <Component spec={spec} data={data} expanded />

            <details className="rounded-[18px] border border-border bg-card p-4 text-[13px]">
              <summary className="cursor-pointer select-none">Xem cách tính</summary>
              <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1">
                <dt className="text-muted-foreground">Trường dữ liệu</dt>
                <dd className="break-words">{spec.fields.join(", ") || "—"}</dd>
                <dt className="text-muted-foreground">Đơn vị</dt>
                <dd>{spec.unit ?? "—"}</dd>
                <dt className="text-muted-foreground">Phiên dữ liệu</dt>
                <dd>{data.as_of}</dd>
                <dt className="text-muted-foreground">Lời gọi công cụ</dt>
                <dd className="break-words">{spec.tool_call_ids.join(", ") || "—"}</dd>
                <dt className="text-muted-foreground">Mã lát dữ liệu</dt>
                <dd className="break-all">{spec.descriptor_id}</dd>
              </dl>
            </details>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
