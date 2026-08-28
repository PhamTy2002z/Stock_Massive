"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * The settings surface is built from three pieces that repeat: a titled
 * section, a bordered panel, and a row whose label sits left and whose control
 * sits right. Elevation is carried by the surface step (the panel one stop
 * above the dialog it sits in), never by a shadow, so the panel ships flat with
 * one hairline.
 */

export function SettingsSection({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    /* One section is on screen at a time — the dialog's rail switches between
       them rather than scrolling past them — so the heading is the pane's own
       title, not an anchor to jump to. */
    <section className="animate-vg-row-in">
      <h2 className="text-[1.45rem] font-semibold leading-[1.19] tracking-[-0.02em]">
        {title}
      </h2>
      {description ? (
        <p className="mt-2 text-meta text-ink-4">
          {description}
        </p>
      ) : null}
      <div className="mt-5 space-y-6">{children}</div>
    </section>
  )
}

export function SettingsPanel({
  children,
  footer,
}: {
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  return (
    <div className="overflow-hidden rounded-card border border-hairline bg-card">
      {children}
      {footer ? (
        <div className="border-t border-hairline bg-foreground/[0.025] px-5 py-3">
          {footer}
        </div>
      ) : null}
    </div>
  )
}

export function SettingsRow({
  label,
  description,
  children,
  className,
}: {
  label: string
  description?: string
  children?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        // Below md the control drops under its label rather than fighting it
        // for a share of a phone-width row.
        "flex flex-col gap-3 border-b border-hairline px-5 py-4 last:border-b-0 md:flex-row md:items-center md:justify-between md:gap-6",
        className
      )}
    >
      <div className="min-w-0 md:max-w-[280px]">
        <div className="text-[0.95rem] font-medium">
          {label}
        </div>
        {description ? (
          <p className="mt-0.5 text-meta text-ink-6">
            {description}
          </p>
        ) : null}
      </div>
      {children ? <div className="min-w-0 md:shrink-0">{children}</div> : null}
    </div>
  )
}

/**
 * Read-only value in a field-shaped shell — it looks like the input it would be
 * if the field were editable, but it is deliberately not one.
 */
export function ReadOnlyField({ value }: { value: string }) {
  return (
    <div className="w-full truncate rounded-lg border border-hairline bg-background px-3 py-2 text-meta tabular-nums text-ink-4 md:w-[250px]">
      {value}
    </div>
  )
}

/** Where an allowance stands: comfortable, close, or spent. */
export type MeterTone = "normal" | "caution" | "spent"

const TONE: Record<MeterTone, { bar: string; figure: string }> = {
  // Not the amber: it is rationed to one filled control per view, and a meter
  // sitting at a third is not that control. Ink carries the neutral case, and
  // the two states that want attention borrow the vocabulary the provenance
  // strip already uses for the same idea.
  normal: { bar: "bg-ink-4", figure: "text-foreground" },
  caution: { bar: "bg-caution", figure: "text-caution" },
  spent: { bar: "bg-negative", figure: "text-negative" },
}

/**
 * One allowance as a figure and a bar.
 *
 * The figure leads and the bar follows, rather than the reverse: the reader's
 * question is "how many left", which is a number, and the bar is only there to
 * make the answer legible at a glance. A bar alone would turn a countable
 * allowance into an impression of one.
 *
 * `role="meter"` rather than `progressbar` — this reports a level within a
 * known range, not progress toward completion — and the value is announced as
 * text as well, because a meter conveying its state only through the width of
 * a div says nothing to a reader who cannot see it.
 *
 * `label` is required rather than optional, and is not the same thing as the
 * row's visible label: that one is a heading beside the control, not a name
 * attached to it, so a reader arriving on the meter alone would otherwise hear
 * a figure with nothing to say what it measured.
 */
export function AllowanceMeter({
  label,
  value,
  ceiling,
  tone,
  figure,
  note,
}: {
  /** What this allowance is of, for a reader who cannot see the row it sits in. */
  label: string
  value: number
  ceiling: number
  tone: MeterTone
  /** The reader-facing form of the numbers, already rounded and worded. */
  figure: string
  note?: string
}) {
  // A spent allowance still draws a full bar rather than overflowing it: going
  // over a ceiling is what the tone says, and a bar wider than its track would
  // just look broken.
  const filled = ceiling <= 0 ? 0 : Math.min(100, Math.round((value / ceiling) * 100))
  const palette = TONE[tone]

  return (
    <div className="w-full md:w-[250px]">
      <div
        className={cn(
          "text-right font-mono text-[0.95rem] tabular-nums",
          palette.figure
        )}
      >
        {figure}
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={ceiling}
        aria-valuetext={figure}
        className="mt-1.5 h-1.5 w-full overflow-hidden rounded-pill bg-foreground/[0.09]"
      >
        <div
          className={cn("h-full rounded-pill transition-[width] duration-300", palette.bar)}
          style={{ width: `${filled}%` }}
        />
      </div>
      {note ? <p className="mt-1.5 text-right text-micro text-ink-6">{note}</p> : null}
    </div>
  )
}
