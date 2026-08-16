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
        "rounded-full bg-card text-[13px] leading-[1.29] tracking-[-0.224px]",
        "transition-transform duration-150 active:scale-95",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        // The active pill takes its extra weight from a 2px border, so the
        // label never shifts by a pixel when selection moves between chips.
        isActive
          ? "border-2 border-interactive-strong px-[13px] py-1.5 font-semibold"
          : "border border-border px-3.5 py-[7px] text-muted-foreground hover:text-foreground"
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
      className="flex size-9 shrink-0 items-center justify-center rounded-full text-interactive transition-[background-color,transform] duration-150 hover:bg-muted active:scale-95 disabled:cursor-progress"
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
      <h2 className="text-2xl font-semibold leading-[1.2] tracking-[-0.374px]">{title}</h2>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  )
}
