"use client"

import { cn } from "@/lib/utils"

/**
 * A value marked against the low–high bounds it sits between.
 *
 * Extracted from the three range cards on the stock overview, which is the
 * primitive ADR-0012 says the `relative_position` Widget is informed by. Same
 * mechanical split as the comparison leaf: the card decides what the bounds
 * mean, the leaf draws a position on a track, and neither knows how the other
 * got its numbers.
 *
 * The percentage is the caller's, already clamped. Clamping here would hide the
 * case worth seeing — a stale quote outside its own session range is a data
 * problem, and a leaf that silently pins it to 100% is a leaf that hides one.
 */
export interface RangeTrackProps {
  /** Where the value sits, 0–100. */
  percent: number
  /** CSS colour for the filled portion. */
  fillColor: string
  /** CSS colour for the track. */
  trackColor: string
  /** CSS colour for the marker sitting at `percent`. */
  markerColor: string
  /** CSS colour for the ring that separates the marker from the surface. */
  markerRingColor?: string
  className?: string
}

export function RangeTrack({
  percent,
  fillColor,
  trackColor,
  markerColor,
  markerRingColor,
  className,
}: RangeTrackProps) {
  return (
    <div
      className={cn("relative h-1.5 rounded-full", className)}
      style={{ backgroundColor: trackColor }}
    >
      <span
        style={{ width: `${percent}%`, backgroundColor: fillColor }}
        className="absolute inset-y-0 left-0 rounded-full"
      />
      <span
        style={{
          left: `${percent}%`,
          backgroundColor: markerColor,
          borderColor: markerRingColor,
        }}
        className={cn(
          "absolute -top-[3px] -ml-1.5 size-3 rounded-full",
          markerRingColor && "border-2"
        )}
      />
    </div>
  )
}
