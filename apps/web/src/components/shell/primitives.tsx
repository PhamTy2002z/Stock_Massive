"use client"

import { forwardRef, useId, type ButtonHTMLAttributes, type ReactNode } from "react"

import { cn } from "@/lib/utils"

/**
 * What an unfinished control says about itself.
 *
 * Named once because two things read it now: the badge the eye sees and the
 * description a screen reader is pointed at. Two copies would let one of them
 * drift into saying something the other does not.
 */
export const COMING_SOON = "Sắp ra mắt"

/**
 * The handful of shapes the whole shell is drawn from.
 *
 * Every one of them exists because the reference repeats it verbatim in five or
 * six places — a 30px icon button, a menu row, a raised card, a mono figure. A
 * component that re-typed the classes each time would drift a pixel per copy,
 * and the surface separates its planes by tone rather than by rules, so a card
 * that picked the wrong step stops reading as a card at all.
 */

/**
 * Who is signed in, as a single letter.
 *
 * The one place the amber meets the board's yellow. A gradient rather than a
 * flat fill, and ink-on-light rather than the reverse: it is the same reading as
 * the filled button — a lit surface carrying dark type — which is what keeps an
 * avatar from looking like a status dot.
 */
export function Avatar({ initial, className }: { initial: string; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-6 shrink-0 items-center justify-center rounded-full bg-[linear-gradient(120deg,hsl(var(--reference)),hsl(var(--primary)))] text-micro font-semibold text-surface-ground",
        className,
      )}
    >
      {initial}
    </span>
  )
}

/** A raised card: the step the page's own content sits on. */
export function Card({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn("rounded-card border border-border bg-surface-raised p-3.5", className)}>
      {children}
    </div>
  )
}

/** The same card, one step up, for content nested *inside* a panel. */
export function PanelCard({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn("rounded-xl border border-border bg-surface-sunken p-3", className)}>
      {children}
    </div>
  )
}

/** The quietest label the system has: uppercase, tracked out, ink-6. */
export function Eyebrow({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <span className={cn("text-eyebrow font-semibold uppercase text-ink-6", className)}>
      {children}
    </span>
  )
}

/** Any number a reader might compare against another number. */
export function Figure({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return <span className={cn("font-mono tabular-nums", className)}>{children}</span>
}

/**
 * A 30px square control carrying only an icon.
 *
 * `title` and an accessible name are required together rather than optional:
 * the reference's chrome is almost entirely iconographic, and a row of unnamed
 * squares is unusable by anything that is not a pair of eyes.
 */
export const IconButton = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { label: string; size?: "sm" | "md" }
>(function IconButton({ label, size = "md", className, children, ...props }, ref) {
  return (
    <button
      ref={ref}
      type="button"
      title={label}
      aria-label={label}
      {...props}
      className={cn(
        "flex shrink-0 items-center justify-center rounded-lg text-ink-5 transition-colors",
        "hover:bg-foreground/[0.06] hover:text-foreground",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:pointer-events-none disabled:opacity-40",
        size === "sm" ? "size-7" : "size-[30px]",
        className,
      )}
    >
      {children}
    </button>
  )
})

/** The floating surface every popover and dropdown is drawn on. */
export function Menu({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      role="menu"
      onClick={(event) => event.stopPropagation()}
      className={cn(
        "z-30 animate-vg-row-in rounded-[14px] border border-border bg-surface-menu p-1.5 shadow-menu",
        className,
      )}
    >
      {children}
    </div>
  )
}

export function MenuItem({
  icon,
  children,
  hint,
  trailing,
  destructive = false,
  onClick,
  disabled = false,
  quiet = false,
}: {
  icon?: ReactNode
  children: ReactNode
  /** A keyboard shortcut, set in mono against the right edge. */
  hint?: string
  trailing?: ReactNode
  destructive?: boolean
  onClick?: () => void
  disabled?: boolean
  /**
   * Say the row is unavailable without drawing the chip that says it.
   *
   * The chip is ~84px of uppercase micro type — wider than the label on a
   * contextual menu, so one inert row would set the width of the whole menu.
   * The reason is still written and still pointed at by `aria-describedby`;
   * only the eye loses it, and the eye already has a row at 40% opacity that
   * does not answer the pointer.
   */
  quiet?: boolean
}) {
  // Generated rather than derived from the label: two menus can be open on one
  // page, and two rows can carry the same words.
  const badgeId = useId()
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      disabled={disabled}
      // A badge only the eye can see says nothing about *why* this row cannot be
      // pressed. Pointed at the badge's own text so the reason is announced with
      // the row rather than left to be inferred from it being inert.
      aria-describedby={disabled ? badgeId : undefined}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-[9px] px-2.5 py-2 text-left text-row transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:pointer-events-none disabled:opacity-40",
        destructive
          ? "text-destructive hover:bg-destructive/10"
          : "text-ink-2 hover:bg-foreground/[0.06]",
      )}
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {hint && <span className="shrink-0 font-mono text-micro text-ink-6">{hint}</span>}
      {disabled && (
        <span
          id={badgeId}
          className={
            quiet
              ? "sr-only"
              : "shrink-0 rounded-md border border-border px-1.5 py-0.5 text-micro font-medium uppercase tracking-[0.04em] text-ink-5"
          }
        >
          {COMING_SOON}
        </span>
      )}
      {trailing}
    </button>
  )
}

export function MenuSeparator() {
  return <span className="mx-1.5 my-1.5 block h-px bg-border" aria-hidden="true" />
}

/**
 * The colour a change is allowed to be.
 *
 * Green and red are data here and never brand — the amber is the filled control
 * and nothing else, so a rising number must not borrow it. Flat is the board's
 * reference yellow, because unchanged is a state the Vietnamese board names
 * rather than an absence.
 */
export function deltaClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "text-ink-4"
  if (value > 0) return "text-positive"
  if (value < 0) return "text-negative"
  return "text-reference"
}

/** A signed percentage in the Vietnamese convention: comma decimal, unicode minus. */
export function signedPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—"
  const sign = value > 0 ? "+" : value < 0 ? "−" : ""
  return `${sign}${Math.abs(value).toFixed(digits).replace(".", ",")}%`
}

/** A price, grouped the way a Vietnamese board groups it. */
export function price(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—"
  return Math.round(value).toLocaleString("vi-VN")
}

/**
 * A horizontal meter that grows from its own left edge on first paint.
 *
 * The growth is the point: a bar that was always its width reads as a printed
 * figure, and these are all comparisons the reader is meant to watch resolve.
 */
export function Bar({
  width,
  className,
  delay = 0,
  track = true,
}: {
  /** A CSS width — a percentage in practice. */
  width: string
  className?: string
  delay?: number
  track?: boolean
}) {
  return (
    <span
      className={cn(
        "block h-[5px] overflow-hidden rounded-pill",
        track && "bg-foreground/[0.08]",
      )}
    >
      <i
        className={cn("block h-full animate-vg-bar-grow rounded-pill", className)}
        style={{ width, animationDelay: `${delay}ms` }}
      />
    </span>
  )
}

/**
 * How strongly a sector tile is tinted, given the session's own extreme.
 *
 * Scaled against the day rather than against a fixed percentage. A fixed
 * divisor was tuned for the reference's −3.4% day and paints a real ±0.5%
 * session in tints too faint to read as a heat map at all — which defeats the
 * only thing the wall is for. The floor keeps the quietest tile visible and the
 * ceiling keeps the loudest from out-shouting the board beside it.
 */
export function sectorTint(changePct: number, peak: number): string {
  const scale = Math.max(peak, 0.4)
  const alpha = 0.06 + Math.min(1, Math.abs(changePct) / scale) * 0.24
  const token = changePct > 0 ? "--positive" : "--negative"
  return `hsl(var(${token}) / ${alpha.toFixed(3)})`
}

/** The loudest move in a set of sectors, for `sectorTint` to scale against. */
export function peakChange(rows: { change_pct: number }[]): number {
  return rows.reduce((highest, row) => Math.max(highest, Math.abs(row.change_pct)), 0)
}

/** The empty/loading line the shell uses instead of a spinner in a list. */
export function QuietLine({ children }: { children: ReactNode }) {
  return <p className="px-2.5 py-2 text-meta leading-relaxed text-ink-6">{children}</p>
}

/**
 * Marks a surface whose figures are the reference's own rather than this
 * account's, because the API has no endpoint behind it yet.
 *
 * Visible on purpose. A placeholder that looked identical to live data would be
 * the one failure mode worth avoiding on a surface people make money decisions
 * on — so the panel says so, in the panel, every time.
 */
export function SampleDataNote({ children }: { children?: ReactNode }) {
  return (
    <p
      role="note"
      className="flex items-start gap-2 rounded-lg border border-caution/45 bg-caution/[0.1] px-2.5 py-2 text-micro leading-relaxed text-ink-3"
    >
      <i className="mt-[5px] block size-1.5 shrink-0 rounded-full bg-caution" aria-hidden="true" />
      <span>
        <strong className="block font-semibold uppercase tracking-[0.04em] text-caution">
          Dữ liệu minh họa · Không dùng để ra quyết định
        </strong>
        <span className="mt-0.5 block">
          {children ?? "API chưa phục vụ mục này."}
        </span>
      </span>
    </p>
  )
}

/** Marks an illustrative panel before the reader reaches any of its figures. */
export function SampleBadge() {
  return (
    <span className="rounded-md border border-caution/40 bg-caution/[0.1] px-1.5 py-0.5 text-micro font-semibold uppercase tracking-[0.05em] text-caution">
      Minh họa
    </span>
  )
}

/** A capability-shaped surface that is present but not connected yet. */
export function UnavailableNote({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="rounded-lg border border-border bg-foreground/[0.035] px-2.5 py-2 text-micro leading-relaxed text-ink-4">
      <strong className="block font-semibold uppercase tracking-[0.04em] text-ink-3">
        Tính năng sắp ra mắt
      </strong>
      <span className="mt-0.5 block">{children}</span>
    </p>
  )
}
