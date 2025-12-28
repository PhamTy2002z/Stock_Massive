"use client"

import { cn } from "@/lib/utils"

interface PremiumBadgeProps {
  value: number | null
  className?: string
}

/**
 * 5-tier color coding for better tracking:
 * - Vượt trội (>30%): Bright green, high intensity
 * - Tốt (+10% to +30%): Light green
 * - Trung bình (±10%): Neutral gray
 * - Kém (-10% to -30%): Light red
 * - Rất kém (<-30%): Bright red, high intensity
 */
const getPremiumStyles = (value: number) => {
  // Tier 1: Vượt trội (>30%)
  if (value > 30) {
    return {
      bg: "bg-emerald-500/20",
      text: "text-emerald-400",
      border: "ring-1 ring-emerald-500/30",
    }
  }
  // Tier 2: Tốt (+10% to +30%)
  if (value > 10) {
    return {
      bg: "bg-[hsl(var(--stock-up))]/10",
      text: "text-[hsl(var(--stock-up))]",
      border: "",
    }
  }
  // Tier 3: Trung bình (±10%)
  if (value >= -10) {
    return {
      bg: "bg-muted",
      text: "text-muted-foreground",
      border: "",
    }
  }
  // Tier 4: Kém (-10% to -30%)
  if (value >= -30) {
    return {
      bg: "bg-[hsl(var(--stock-down))]/10",
      text: "text-[hsl(var(--stock-down))]",
      border: "",
    }
  }
  // Tier 5: Rất kém (<-30%)
  return {
    bg: "bg-red-500/20",
    text: "text-red-400",
    border: "ring-1 ring-red-500/30",
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
        styles.border,
        className
      )}
    >
      {value > 0 ? "+" : ""}{value.toFixed(1)}%
    </span>
  )
}
