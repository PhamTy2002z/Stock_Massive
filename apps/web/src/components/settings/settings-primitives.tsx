"use client"

import * as React from "react"
import { ChevronDown } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * The settings surface is built from a titled section and a stack of rows whose
 * label sits left and whose control sits right. Rows are separated by a
 * hairline rather than boxed into a card: one section is on screen at a time,
 * so a border around the whole stack would only draw a frame around the pane it
 * already fills.
 *
 * **Half of what this surface offers is not built yet.** The reference design
 * asks for notification channels, a profile, security and data controls that
 * have no backend behind them. Every such row keeps its real shape and carries
 * `soon` — a badge beside the label and an inert control — because a row that
 * looked live and silently did nothing is the one presentation guaranteed to
 * read as a bug.
 */

export function SettingsSection({
  title,
  description,
  children,
  footer,
}: {
  title: string
  description?: string
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  return (
    /* The rail switches between panes rather than scrolling past them, so the
       heading is the pane's own title, not an anchor to jump to. */
    <section className="animate-vg-row-in">
      <h2 className="text-[1.25rem] font-semibold leading-[1.24] tracking-[-0.01em]">
        {title}
      </h2>
      {description ? (
        <p className="mt-1.5 max-w-[56ch] text-control text-ink-4">{description}</p>
      ) : null}
      <div className="mt-4">{children}</div>
      {footer ? <p className="mt-[18px] text-micro text-ink-6">{footer}</p> : null}
    </section>
  )
}

/** Says a row is drawn but not wired, right where the reader would press it. */
export function SoonBadge() {
  return (
    <span className="shrink-0 rounded-pill border border-hairline bg-foreground/[0.04] px-2 py-[0.15rem] text-[0.68rem] font-medium leading-[1.1] text-ink-6">
      Sắp ra mắt
    </span>
  )
}

export function SettingsRow({
  label,
  description,
  soon,
  children,
  className,
}: {
  label: string
  description?: string
  /** The control is drawn inert and the label carries a badge saying why. */
  soon?: boolean
  children?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        // Below md the control drops under its label rather than fighting it
        // for a share of a phone-width row.
        "flex flex-col gap-3 border-b border-hairline py-[22px] first:pt-[26px] last:border-b-0 md:flex-row md:items-center md:justify-between md:gap-8",
        className
      )}
    >
      <div className="min-w-0 md:flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[0.95rem] font-medium">{label}</span>
          {soon ? <SoonBadge /> : null}
        </div>
        {description ? (
          <p className="mt-1 max-w-[52ch] text-control text-ink-6 [text-wrap:pretty]">
            {description}
          </p>
        ) : null}
      </div>
      {children ? (
        <div className={cn("min-w-0 md:flex-none", soon && "opacity-60")}>{children}</div>
      ) : null}
    </div>
  )
}

/**
 * A segmented picker: two or three mutually exclusive choices, drawn as one
 * control rather than as a row of buttons.
 *
 * Selection is a raised neutral, not the amber — the accent is rationed to
 * filled actions, and choosing a colour mode is not one. The pill is the menu
 * surface because that is the one step that lifts on both grounds, where a
 * fixed alpha would vanish into one of them.
 */
export function Segmented<T>({
  label,
  options,
  selected,
  onSelect,
}: {
  label: string
  options: { value: T; label: string; icon?: React.ReactNode }[]
  /** `null` before the browser's own choice has been read. */
  selected: T | null
  onSelect: (value: T) => void
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="flex w-full gap-0.5 rounded-[11px] border border-hairline bg-surface-sunken p-[3px] md:w-auto"
    >
      {options.map((option) => {
        const active = selected === option.value
        return (
          <button
            key={String(option.value)}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onSelect(option.value)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-[8px] px-3 py-1.5 text-control leading-[1.25] outline-none transition-[background-color,color] duration-150 focus-visible:ring-2 focus-visible:ring-ring md:flex-none",
              active
                ? "bg-surface-menu text-foreground shadow-sm"
                : "text-ink-6 hover:text-foreground"
            )}
          >
            {option.icon}
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

/**
 * One binary setting.
 *
 * The amber fills the track when the setting is on. This is the one place the
 * accent is spent on something other than a button: a switch reports state, and
 * on a night ground an ink-filled track at 22px tall does not read as *on* at
 * all — it reads as a slightly different grey.
 *
 * The knob is the top of the ink ladder, which inverts with the theme: near
 * white on the night ground, near black on paper. A knob pinned to `#fff` would
 * disappear into the light theme's own amber.
 */
export function Toggle({
  label,
  checked,
  onChange,
  disabled,
}: {
  /** What this switches, for a reader arriving on the control alone. */
  label: string
  checked: boolean
  onChange?: (next: boolean) => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-label={label}
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange?.(!checked)}
      className={cn(
        "relative block h-[22px] w-[38px] shrink-0 rounded-pill outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        checked ? "bg-primary" : "bg-foreground/[0.14]",
        disabled ? "cursor-not-allowed" : "cursor-pointer"
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "absolute top-[3px] size-4 rounded-full bg-ink-1 transition-[left] duration-200",
          checked ? "left-[19px]" : "left-[3px]"
        )}
      />
    </button>
  )
}

/**
 * A choice that will be a menu once there is something to choose between.
 *
 * Drawn as the trigger it will become — current value, chevron — and inert,
 * because the alternatives it would list are all unbuilt. Not a `<select>`
 * with one option: that opens, offers the reader nothing, and closes.
 */
export function SelectStub({
  label,
  value,
  mono,
}: {
  label: string
  value: string
  /** Values that name a typeface or a figure are shown in it. */
  mono?: boolean
}) {
  return (
    <span
      role="button"
      aria-disabled="true"
      aria-label={label}
      className={cn(
        "flex cursor-not-allowed items-center gap-1.5 text-control text-ink-3",
        mono && "font-mono"
      )}
    >
      {value}
      <ChevronDown className="size-[13px] shrink-0 text-ink-6" strokeWidth={1.8} />
    </span>
  )
}

/**
 * A pill-shaped action beside a row.
 *
 * `danger` outlines in the negative rather than filling with it: the row it
 * sits in is one of several, and a solid red button in a settings list reads as
 * an alarm the pane is not raising.
 */
export function PillAction({
  children,
  tone = "neutral",
  disabled,
  onClick,
}: {
  children: React.ReactNode
  tone?: "neutral" | "danger"
  disabled?: boolean
  onClick?: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "shrink-0 whitespace-nowrap rounded-pill border px-[0.95rem] py-[0.42rem] text-control outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
        tone === "danger"
          ? "border-negative/35 text-negative hover:bg-negative/10"
          : "border-border text-ink-3 hover:bg-accent hover:text-foreground",
        disabled && "cursor-not-allowed hover:bg-transparent"
      )}
    >
      {children}
    </button>
  )
}

/**
 * A text field that keeps its shape while the write path behind it is unbuilt.
 *
 * `readOnly` rather than `disabled`: the reader can still select and copy what
 * is in it, which is the only thing the field is currently good for.
 */
export function TextFieldStub({
  label,
  value,
  placeholder,
  rows,
}: {
  label: string
  value?: string
  placeholder?: string
  /** Set for a multi-line field, which spans the row instead of sitting beside it. */
  rows?: number
}) {
  const shared =
    "w-full rounded-[10px] border border-input bg-surface-sunken px-3 py-2 text-control text-ink-3 outline-none placeholder:text-ink-6"

  if (rows) {
    return (
      <textarea
        aria-label={label}
        readOnly
        rows={rows}
        defaultValue={value}
        placeholder={placeholder}
        className={cn(shared, "block resize-none leading-[1.55]")}
      />
    )
  }

  return (
    <input
      type="text"
      aria-label={label}
      readOnly
      defaultValue={value}
      placeholder={placeholder}
      className={cn(shared, "md:w-[240px]")}
    />
  )
}

/**
 * Read-only value in a field-shaped shell — it looks like the input it would be
 * if the field were editable, but it is deliberately not one.
 */
export function ReadOnlyField({ value }: { value: string }) {
  return (
    <div className="w-full truncate rounded-[10px] border border-hairline bg-surface-sunken px-3 py-2 text-control tabular-nums text-ink-4 md:w-[240px]">
      {value}
    </div>
  )
}

/** Where an allowance stands: comfortable, close, or spent. */
export type MeterTone = "normal" | "caution" | "spent"

const TONE: Record<MeterTone, { bar: string; figure: string }> = {
  // Not the amber: it is spent on the switch track in this dialog, and a meter
  // sitting at a third is not asking for the same attention. Ink carries the
  // neutral case, and the two states that want attention borrow the vocabulary
  // the provenance strip already uses for the same idea.
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
    <div className="w-full md:w-[240px]">
      <div className={cn("text-right font-mono text-[0.95rem] tabular-nums", palette.figure)}>
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
