"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { WIDGET_PALETTE } from "./palette"

/**
 * What every Widget carries whatever it draws.
 *
 * Five of ADR-0012's requirements are the same requirement in five places — a
 * textual summary, a visible data date, a screen-reader label, a data table,
 * and reduced-motion behaviour — so they live here once rather than four times.
 * A component that forgot one would be a component that shipped a picture with
 * no reading beside it, and this frame is why that is not reachable.
 *
 * The table is not a fallback. It is the same data, reached by an ordinary
 * disclosure: `aria-expanded` and `aria-controls` on a real button, and
 * `hidden` on the panel. Collapsed, it is out of the accessibility tree — which
 * is what a disclosure is supposed to do, since the button already announces
 * that it is there. What a screen-reader user must not have to open a
 * disclosure for is the *reading*, and that is why the summary, the data date
 * and each Widget's own per-row description sit outside it.
 */
export interface WidgetFrameProps {
  title: string
  /** The plain-language reading. Never a repetition of the title. */
  summary: string
  /** The date the slice carries, in ISO form. Rendered, never inferred. */
  asOf: string
  /** What a screen reader is told the picture is. */
  figureLabel: string
  /** The data table, which is always rendered and sometimes visible. */
  table: React.ReactNode
  /** Opens the same fixed data full-screen; absent inside the expanded view. */
  onExpand?: () => void
  expanded?: boolean
  className?: string
  children: React.ReactNode
}

/**
 * The data date, formatted the way this product writes one.
 *
 * An unparseable date is shown as it arrived rather than swallowed: a Widget
 * must carry its date visibly, and "Invalid Date" is at least a visible
 * failure, whereas an empty span is a Widget quietly claiming to be undated.
 */
export function formatDataDate(asOf: string): string {
  const parsed = new Date(asOf)
  if (Number.isNaN(parsed.getTime())) return asOf
  return parsed.toLocaleDateString("vi-VN")
}

export function WidgetFrame({
  title,
  summary,
  asOf,
  figureLabel,
  table,
  onExpand,
  expanded = false,
  className,
  children,
}: WidgetFrameProps) {
  // Inside the expanded view the table is the point, so it opens with it. In
  // the transcript the picture leads and the table is one keystroke away.
  const [showTable, setShowTable] = React.useState(expanded)
  const tableId = React.useId()

  return (
    <figure
      className={cn(
        "min-w-0 rounded-card border border-border bg-card p-4",
        // Reduced motion removes the transition rather than shortening it: a
        // fast animation is still an animation to a reader who asked for none.
        "motion-safe:transition-colors motion-reduce:transition-none",
        className
      )}
      style={{ color: WIDGET_PALETTE.ink }}
    >
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-[15px] font-semibold leading-[1.24] tracking-[-0.374px]">
          {title}
        </span>
        <span
          className="text-[13px] leading-[1.43] tracking-[-0.208px]"
          style={{ color: WIDGET_PALETTE.inkMuted }}
        >
          Dữ liệu ngày {formatDataDate(asOf)}
        </span>
      </figcaption>

      {/* The description is a sibling of the drawing rather than an
          `aria-label` on a `role="img"` wrapper. `role="img"` makes every
          descendant presentational, which would have hidden exactly the parts
          worth reaching: the ranked list, and the per-symbol readings each
          Widget writes for a screen reader. A described sibling gives the
          reader the sentence *and* the content. */}
      <p className="sr-only">{figureLabel}</p>
      <div data-widget-figure className="mt-3 w-full min-w-0 overflow-hidden">
        {children}
      </div>

      {/* The reading, in words. Present whether or not the reader can see the
          picture, and never a restatement of the title. */}
      <p className="mt-3 text-[13px] leading-[1.43] tracking-[-0.208px]">{summary}</p>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          aria-expanded={showTable}
          aria-controls={tableId}
          onClick={() => setShowTable((open) => !open)}
          className="rounded-md text-[13px] underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {showTable ? "Ẩn bảng dữ liệu" : "Xem bảng dữ liệu"}
        </button>
        {onExpand && !expanded && (
          <button
            type="button"
            onClick={onExpand}
            className="rounded-md text-[13px] underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Mở rộng
          </button>
        )}
      </div>

      <div id={tableId} hidden={!showTable} className="mt-3 overflow-x-auto">
        {table}
      </div>
    </figure>
  )
}

/**
 * What a Widget renders when the slice is too thin for a useful picture.
 *
 * Bullets or a small table, never an empty chart: an axis with nothing on it
 * says "no data" in the one language a reader is least likely to read it in.
 */
export function TooLittleData({
  title,
  asOf,
  lines,
}: {
  title: string
  asOf: string
  lines: string[]
}) {
  return (
    <figure
      className="min-w-0 rounded-card border border-border bg-card p-4"
      style={{ color: WIDGET_PALETTE.ink }}
    >
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-[15px] font-semibold leading-[1.24] tracking-[-0.374px]">
          {title}
        </span>
        <span
          className="text-[13px] leading-[1.43]"
          style={{ color: WIDGET_PALETTE.inkMuted }}
        >
          Dữ liệu ngày {formatDataDate(asOf)}
        </span>
      </figcaption>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-[13px] leading-[1.43]">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </figure>
  )
}
