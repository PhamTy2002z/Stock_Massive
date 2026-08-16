"use client"

import { formatFieldValue } from "@/components/alpha/widgets/units"
import type { FigureView } from "@/lib/alpha-desk/analysis"
import { priceZoneBand } from "@/lib/alpha-desk/analysis"
import { cn } from "@/lib/utils"
import { CHROME, NARRATION, priceZoneSentence } from "./copy"

/**
 * The only inline graphic the artifact draws.
 *
 * Every other picture deep-links to `/analytics/deep-dive`, because one number
 * lives in one place (`docs/specs/0002` §5) and a second chart here would be a
 * second answer to a question Stock 360 already answers. This one earns its
 * place because the zone *is* a range and a range read as two numbers in a
 * sentence is a range the reader has to draw themselves.
 *
 * **It is a range, not a target.** The band is centred on the anchor close and
 * carries no arrow, no projection and no shading that could be read as a
 * direction — the field is a realized σ computed in code, and it reads that
 * way.
 *
 * A refused zone draws nothing at all and says why. A band shaped from a
 * half-present figure would be a picture standing for nothing.
 */
export function PriceZoneBand({
  zone,
  className,
}: {
  zone: FigureView | null
  className?: string
}) {
  const band = priceZoneBand(zone)

  if (band === null) {
    return (
      <p className={cn("text-xs text-muted-foreground", className)}>
        {zone?.reason ?? NARRATION.zoneRefused}
      </p>
    )
  }

  const lower = formatFieldValue(band.lower, "vnd")
  const upper = formatFieldValue(band.upper, "vnd")
  const anchor = formatFieldValue(band.anchor, "vnd")

  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs">
        <span className="font-medium">{CHROME.priceZone}</span>
        <span className="tabular-nums text-muted-foreground">
          {lower} – {upper}
        </span>
      </div>

      {/* Presentational: the two prices and the anchor are already written out
          above, so the drawing carries no information the text does not. That
          is what lets it be `aria-hidden` rather than a chart a screen reader
          has to narrate. */}
      <svg
        viewBox="0 0 100 8"
        preserveAspectRatio="none"
        aria-hidden
        className="h-2 w-full"
      >
        <rect x="0" y="3" width="100" height="2" rx="1" className="fill-muted" />
        <rect
          x="10"
          y="2"
          width="80"
          height="4"
          rx="2"
          className="fill-sky-500/30 stroke-sky-500/60"
          strokeWidth="0.5"
        />
        <line
          x1="50"
          y1="0"
          x2="50"
          y2="8"
          className="stroke-foreground/70"
          strokeWidth="1"
        />
      </svg>

      <p className="text-[11px] text-muted-foreground">
        {priceZoneSentence(band.halfWidthPct)} {CHROME.asOf}{" "}
        <span className="tabular-nums">{zone?.asOf ?? "—"}</span> · {anchor}
      </p>
    </div>
  )
}
