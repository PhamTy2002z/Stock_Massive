import type { VolumeSpikeAnomalyLevel } from "@/lib/api"

// Anomaly level colors
export const ANOMALY_COLORS: Record<VolumeSpikeAnomalyLevel, string> = {
  normal: "hsl(var(--muted-foreground))",
  elevated: "hsl(45 93% 47%)",
  high: "hsl(0 0% 100%)", // White (was Orange)
  very_high: "hsl(0 84% 60%)",
}

export const ANOMALY_BADGE_VARIANTS: Record<
  VolumeSpikeAnomalyLevel,
  "default" | "secondary" | "destructive" | "outline"
> = {
  normal: "secondary",
  elevated: "outline",
  high: "default",
  very_high: "destructive",
}

// Format helpers
export function formatVolume(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`
  return value.toLocaleString("vi-VN")
}

export function formatRatio(value: number): string {
  return `${value.toFixed(1)}x`
}

// Color indicator for sector headers based on avg_spike_ratio
export function getSectorHeaderColor(avgRatio: number): string {
  if (avgRatio >= 3) return "border-l-4 border-l-red-500"
  if (avgRatio >= 2) return "border-l-4 border-l-white"
  if (avgRatio >= 1.5) return "border-l-4 border-l-yellow-500"
  return "border-l-4 border-l-muted"
}
