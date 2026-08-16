"use client"

import { RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * The three shapes every v3 surface is built from: the 18px card, the pill
 * filter, and the section header with its refresh affordance. Kept in one file
 * so a change to the design system is one edit rather than a sweep.
 */

export function SurfaceCard({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("min-w-0 rounded-card border border-border bg-card p-[14px]", className)}>
      {children}
    </div>
  )
}

export function FilterChip({
  label,
  isActive,
  onClick,
}: {
  label: string
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isActive}
      className={cn(
        "rounded-pill bg-transparent text-control",
        "transition-transform duration-150 active:scale-95",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        // Selection is a lifted plane, not a coloured outline: the teal is the
        // filled action, and a bordered pill wearing it reads as one. Both
        // states carry the same border and the same padding, so the label never
        // shifts by a pixel when selection moves between chips.
        "border px-[13px] py-[7px]",
        isActive
          ? "border-transparent bg-foreground/[0.09] font-medium text-foreground"
          : "border-border text-muted-foreground hover:bg-foreground/[0.04] hover:text-foreground"
      )}
    >
      {label}
    </button>
  )
}

export function RefreshButton({
  onClick,
  isRefreshing = false,
  label,
}: {
  onClick: () => void
  isRefreshing?: boolean
  /** Names what is being refreshed, for screen readers. */
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isRefreshing}
      title="Làm mới"
      className="flex size-9 shrink-0 items-center justify-center rounded-full text-interactive transition-[background-color,transform] duration-150 hover:bg-foreground/[0.06] active:scale-95 disabled:cursor-progress"
    >
      <RefreshCw aria-hidden className={cn("size-[18px]", isRefreshing && "animate-spin")} />
      <span className="sr-only">Làm mới {label}</span>
    </button>
  )
}

export function SectionHeader({
  title,
  children,
  className,
}: {
  title: string
  /** Controls that belong to this section: filters, timestamp, refresh. */
  children?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("mb-3.5 flex flex-wrap items-center justify-between gap-4", className)}>
      <h2 className="text-[1.05rem] font-medium leading-[1.2] tracking-[-0.015em] text-foreground">{title}</h2>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  )
}
