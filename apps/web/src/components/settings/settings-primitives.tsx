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
 * Every row here has a write path behind it. A row the product cannot honour is
 * left out rather than drawn inert: a control that looks live and silently does
 * nothing is the one presentation guaranteed to read as a bug.
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
    /* A pane stacks several of these, 40px apart; the heading is a quiet label
       over its rows rather than a page title, because the rail already names
       the pane. */
    <section className="animate-vg-row-in">
      <h2 className="text-[1rem] font-medium leading-6 tracking-[-0.01em]">{title}</h2>
      {description ? (
        <p className="mt-1 text-control text-ink-5 [text-wrap:pretty]">{description}</p>
      ) : null}
      <div className="mt-3">{children}</div>
    </section>
  )
}

export function SettingsRow({
  label,
  description,
  children,
  className,
}: {
  label: string
  description?: React.ReactNode
  children?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        // Below md the control drops under its label rather than fighting it
        // for a share of a phone-width row.
        "flex min-h-[56px] flex-col gap-3 border-b border-hairline py-3.5 last:border-b-0 md:flex-row md:items-center md:justify-between md:gap-8",
        className
      )}
    >
      <div className="min-w-0 md:flex-1">
        <div className="text-row text-foreground">{label}</div>
        {description ? (
          <p className="mt-0.5 text-control text-ink-5 [text-wrap:pretty]">
            {description}
          </p>
        ) : null}
      </div>
      {children ? <div className="min-w-0 md:flex-none">{children}</div> : null}
    </div>
  )
}

/**
 * A segmented picker: two or three mutually exclusive choices, drawn as one
 * control rather than as a row of buttons.
 *
 * Selection is a raised neutral, not the amber — the accent is rationed to
 * filled actions, and choosing a colour mode is not one. The selected segment is
 * the menu surface because that is the one step that lifts on both grounds,
 * where a fixed alpha would vanish into one of them.
 */
const SEGMENT_TRACK = "flex w-full gap-0.5 rounded-lg bg-foreground/[0.05] p-0.5 md:w-auto"

function segmentItem(active: boolean) {
  return cn(
    "flex h-7 flex-1 items-center justify-center gap-1.5 rounded-md px-3 text-control outline-none transition-[background-color,color] duration-150 focus-visible:ring-2 focus-visible:ring-ring md:flex-none",
    active ? "bg-surface-menu text-foreground shadow-sm" : "text-ink-5 hover:text-foreground"
  )
}

export function Segmented<T>({
  label,
  options,
  selected,
  onSelect,
  iconOnly,
}: {
  label: string
  options: { value: T; label: string; icon?: React.ReactNode }[]
  /** `null` before the browser's own choice has been read. */
  selected: T | null
  onSelect: (value: T) => void
  /** Draw each choice as its icon alone; the label becomes its accessible name. */
  iconOnly?: boolean
}) {
  return (
    <div role="radiogroup" aria-label={label} className={SEGMENT_TRACK}>
      {options.map((option) => {
        const active = selected === option.value
        return (
          <button
            key={String(option.value)}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={iconOnly ? option.label : undefined}
            title={iconOnly ? option.label : undefined}
            onClick={() => onSelect(option.value)}
            className={cn(segmentItem(active), iconOnly && "md:w-8 md:px-0")}
          >
            {option.icon}
            {iconOnly ? null : option.label}
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
        "relative block h-5 w-9 shrink-0 rounded-pill outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        checked ? "bg-primary" : "bg-foreground/[0.14]",
        disabled ? "cursor-not-allowed" : "cursor-pointer"
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "absolute top-0.5 size-4 rounded-full bg-ink-1 transition-[left] duration-200",
          checked ? "left-[18px]" : "left-0.5"
        )}
      />
    </button>
  )
}

/**
 * A compact action beside a row.
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
  label,
  autoFocus,
  type = "button",
}: {
  children: React.ReactNode
  tone?: "neutral" | "danger" | "danger-filled"
  type?: "button" | "submit"
  disabled?: boolean
  onClick?: () => void
  /** An accessible name, where the visible text alone would not say enough. */
  label?: string
  autoFocus?: boolean
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      aria-label={label}
      autoFocus={autoFocus}
      className={cn(
        "h-8 shrink-0 whitespace-nowrap rounded-lg border px-3 text-control outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
        tone === "danger" && "border-negative/35 text-negative hover:bg-negative/10",
        // The second press of a destructive action is the one place a settings
        // row fills with the negative: the reader has already said yes once.
        tone === "danger-filled" && "border-destructive bg-destructive text-destructive-foreground hover:bg-destructive/90",
        tone === "neutral" && "border-border bg-foreground/[0.04] text-foreground hover:bg-foreground/[0.08]",
        disabled && "cursor-not-allowed opacity-60"
      )}
    >
      {children}
    </button>
  )
}

/**
 * A destructive action that asks twice, in place.
 *
 * The first press turns the button into a filled confirmation beside a cancel,
 * and only the second press acts — no `window.confirm`, which would take the
 * question out of the row it is about. Focus moves to the confirmation so a
 * keyboard reader lands on the question they just raised. While the action
 * runs both buttons are disabled and the confirmation says what is happening.
 *
 * `onConfirm` reports its own failure (a toast); this only puts the row back.
 */
export function ConfirmAction({
  children,
  confirmLabel,
  pendingLabel,
  onConfirm,
  disabled,
}: {
  children: React.ReactNode
  confirmLabel: string
  pendingLabel: string
  onConfirm: () => Promise<unknown>
  disabled?: boolean
}) {
  const [phase, setPhase] = React.useState<"idle" | "armed" | "pending">("idle")
  const mounted = React.useRef(true)
  React.useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  if (phase === "idle") {
    return (
      <PillAction tone="danger" disabled={disabled} onClick={() => setPhase("armed")}>
        {children}
      </PillAction>
    )
  }

  const pending = phase === "pending"
  return (
    <div className="flex items-center gap-2">
      <PillAction tone="neutral" disabled={pending} onClick={() => setPhase("idle")}>
        Cancel
      </PillAction>
      <PillAction
        tone="danger-filled"
        autoFocus
        disabled={pending}
        onClick={async () => {
          setPhase("pending")
          try {
            await onConfirm()
          } catch {
            // Reported by the caller; the row only has to stop saying "…ing".
          } finally {
            if (mounted.current) setPhase("idle")
          }
        }}
      >
        {pending ? pendingLabel : confirmLabel}
      </PillAction>
    </div>
  )
}

/** The shared shell of every editable field: 32px, sunken, a visible focus ring. */
export const FIELD =
  "w-full rounded-lg border border-input bg-surface-sunken px-3 text-control text-foreground outline-none transition-colors placeholder:text-ink-6 focus-visible:border-ink-6 focus-visible:ring-2 focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-60"

/**
 * One line of text that saves itself when the reader leaves it or presses Enter.
 *
 * The draft is local, so typing costs no request; the commit happens only when
 * the trimmed text differs from what was saved. A `required` field emptied out
 * goes back to the saved value instead of being sent. A commit that rejects
 * puts the saved value back, because a field showing an edit the server
 * refused would say something that is not true.
 */
export function TextField({
  label,
  value,
  placeholder,
  maxLength,
  required,
  disabled,
  onCommit,
}: {
  label: string
  value: string
  placeholder?: string
  maxLength?: number
  required?: boolean
  disabled?: boolean
  onCommit: (next: string) => Promise<unknown>
}) {
  const [draft, setDraft] = React.useState(value)
  const inflight = React.useRef<string | null>(null)

  // A new saved value — this field's own commit, or another tab's — replaces
  // the draft.
  React.useEffect(() => setDraft(value), [value])

  const commit = async () => {
    const next = draft.trim()
    if (next === value || next === inflight.current) {
      setDraft(value)
      return
    }
    if (required && next === "") {
      setDraft(value)
      return
    }
    inflight.current = next
    try {
      await onCommit(next)
    } catch {
      setDraft(value)
    } finally {
      inflight.current = null
    }
  }

  return (
    <input
      type="text"
      aria-label={label}
      value={draft}
      placeholder={placeholder}
      maxLength={maxLength}
      disabled={disabled}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => void commit()}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault()
          void commit()
        }
      }}
      className={cn(FIELD, "h-8 md:w-56")}
    />
  )
}

/**
 * A native `<select>`, drawn as the quiet trigger the rest of the pane uses.
 *
 * Native on purpose: the platform's own menu is keyboard- and screen-reader-
 * correct on every device, and a phone gets its own picker. `appearance-none`
 * removes the browser's arrow so the chevron can match the pane's icons.
 * The empty string is the "not chosen" option.
 */
export function SelectField({
  label,
  value,
  options,
  disabled,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  disabled?: boolean
  onChange: (next: string) => void
}) {
  return (
    <div className="relative -ml-2.5 w-fit md:ml-0">
      <select
        aria-label={label}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-8 cursor-pointer appearance-none rounded-lg bg-transparent pl-2.5 pr-8 text-control text-foreground outline-none transition-colors hover:bg-foreground/[0.045] focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value} className="bg-surface-menu text-foreground">
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-5"
        strokeWidth={1.7}
      />
    </div>
  )
}

/**
 * Read-only value in a field-shaped shell — it looks like the input it would be
 * if the field were editable, but it is deliberately not one.
 */
export function ReadOnlyField({ value }: { value: string }) {
  return (
    <div className="h-8 w-full truncate rounded-lg border border-hairline bg-surface-sunken px-3 text-control leading-[30px] tabular-nums text-foreground md:w-56">
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
    <div className="w-full md:w-56">
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
