"use client"

import * as React from "react"
import Link from "next/link"
import { parseWidgetRefusals, parseWidgetSpecs } from "./spec"
import type { WidgetData, WidgetSpec } from "./types"
import { WidgetExpand } from "./widget-expand"
import { WidgetSlot } from "./widget-slot"

/**
 * Everything one answer draws, under the ceiling one answer is allowed.
 *
 * The transcript mounts this once per assistant message and hands it the raw
 * message content. It owns three things the individual slots cannot:
 *
 * **The ceiling.** One Widget per answer, and a second only where the user
 * asked for two. That rule is decided by `apps/api`, which is the only side
 * holding the user's text, and it is applied *before* the specs are persisted —
 * so a message can never legitimately carry more than the answer was allowed.
 * What is left for here is a hard bound, not a second opinion: an older build's
 * message, or a bug, must not be able to spray a transcript with pictures. The
 * bound is deliberately not re-derived from `requested`, which records whether
 * the user asked for *a* visual and would say nothing about whether they asked
 * for *two*.
 *
 * **Expand.** One dialog for the whole message rather than one per slot, so two
 * Widgets cannot both be open and the expanded view always shows the data the
 * reader just clicked.
 *
 * **The deep link.** A selection refused because Stock 360 already owns that
 * chart is the one refusal worth showing: it is not a broken picture, it is a
 * pointer to the screen that has the real one.
 */
/**
 * The most any answer may draw, whatever it was persisted carrying.
 *
 * Two, because two is what the server's own ceiling allows at its most
 * permissive. This is the backstop; the one-versus-two decision is the
 * server's.
 */
export const MAX_WIDGETS_PER_ANSWER = 2

export interface MessageWidgetsProps {
  /** The assistant message's `id`, which is how its data is read back. */
  messageId: number
  /** The message's `widgets` array, straight off the transcript. */
  widgets: unknown
  /** The message's `widget_refusals` array. */
  refusals?: unknown
  resolve: (spec: WidgetSpec) => Promise<WidgetData>
  className?: string
}

export function MessageWidgets({
  widgets,
  refusals,
  resolve,
  className,
}: MessageWidgetsProps) {
  const specs = React.useMemo(() => parseWidgetSpecs(widgets), [widgets])
  const links = React.useMemo(() => parseWidgetRefusals(refusals), [refusals])
  const [open, setOpen] = React.useState<{
    spec: WidgetSpec
    data: WidgetData
  } | null>(null)

  const shown = specs.slice(0, MAX_WIDGETS_PER_ANSWER)

  if (shown.length === 0 && links.length === 0) return null

  return (
    <div className={className}>
      {shown.map((spec) => (
        <WidgetSlot
          key={spec.descriptor_id}
          spec={spec}
          resolve={resolve}
          onExpand={(expandedSpec, data) => setOpen({ spec: expandedSpec, data })}
          className="mt-3"
        />
      ))}
      {links.map((refusal) => (
        <p key={refusal.deep_link} className="mt-3 text-meta">
          <Link
            href={refusal.deep_link as string}
            className="underline underline-offset-2"
          >
            Xem biểu đồ này trên màn hình phân tích chi tiết
          </Link>
        </p>
      ))}
      <WidgetExpand
        spec={open?.spec ?? null}
        data={open?.data ?? null}
        onOpenChange={(next) => {
          if (!next) setOpen(null)
        }}
      />
    </div>
  )
}
