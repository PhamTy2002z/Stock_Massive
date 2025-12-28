"use client"

import { cn } from "@/lib/utils"

interface PremiumBadgeProps {
  value: number | null
  className?: string
}

/**
 * Color coding per design-guidelines.md:
 * - Premium (above median): --stock-up (green)
 * - Neutral (±5%): muted foreground (gray)
 * - Discount (below median): --stock-down (red)
 */
const getPremiumStyles = (value: number) => {
  if (value > 5) {
    return {
      bg: "bg-[hsl(var(--stock-up))]/10",
      text: "text-[hsl(var(--stock-up))]",
    }
  }
  if (value >= -5) {
    return {
      bg: "bg-muted",
      text: "text-muted-foreground",
    }
  }
  return {
    bg: "bg-[hsl(var(--stock-down))]/10",
    text: "text-[hsl(var(--stock-down))]",
  }
}

export function PremiumBadge({ value, className }: PremiumBadgeProps) {
  if (value === null) {
    return <span className="text-muted-foreground">-</span>
  }

  const styles = getPremiumStyles(value)

  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold tabular-nums",
        styles.bg,
        styles.text,
        className
      )}
    >
      {value > 0 ? "+" : ""}{value.toFixed(1)}%
    </span>
  )
}
