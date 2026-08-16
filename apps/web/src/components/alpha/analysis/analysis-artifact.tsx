"use client"

import * as React from "react"
import Link from "next/link"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { Maximize2, Minimize2, X } from "lucide-react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useIsMobile } from "@/hooks/use-mobile"
import type { AnalysisArtifact as Artifact } from "@/lib/alpha-desk/analysis"
import { cn } from "@/lib/utils"
import { AxisPanel } from "./axis-panel"
import { Briefing } from "./briefing"
import { AXIS_LABEL, CHROME } from "./copy"
import { PriceZoneBand } from "./price-zone-band"
import { ArtifactRiskNotice } from "./risk-notice"
import { VerdictHeader } from "./verdict-header"

/**
 * An Analysis as the user reads it: inline and bounded, or expanded.
 *
 * **Inline is bounded on purpose.** A Thread may hold ten of these, and ten
 * unbounded briefings is a transcript nobody can scroll. So the inline
 * treatment pins the verdict and the price-zone band and puts the four axes
 * behind tabs — one axis of figures at a time, at a height the next message is
 * still visible under.
 *
 * **The lead axis opens first, and that is the whole of what emphasis buys.**
 * The tab order is the template's order, always; the model chose which one is
 * open and how much it says, never where it sits (`docs/specs/0002` §5).
 *
 * **Expanded is the briefing.** On a wide viewport it takes the full width of
 * the transcript in place; on a narrow one it is a modal overlay rather than a
 * desktop layout forced through a phone (`docs/specs/0002` §8). Radix owns the
 * focus trap and the Escape key for the overlay case.
 */
export function AnalysisArtifact({
  artifact,
  className,
}: {
  artifact: Artifact
  className?: string
}) {
  const [expanded, setExpanded] = React.useState(false)
  const isMobile = useIsMobile()

  return (
    <div
      className={cn(
        "rounded-lg border border-border/60 bg-background/60",
        className,
      )}
      data-testid="analysis-artifact"
    >
      <div className="flex items-start justify-between gap-2 px-3 pt-3">
        <VerdictHeader artifact={artifact} />
        <button
          type="button"
          onClick={() => setExpanded((open) => !open)}
          aria-expanded={expanded}
          className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border/60 px-2 py-1 text-[11px] hover:bg-muted"
        >
          {expanded ? (
            <Minimize2 className="h-3 w-3" />
          ) : (
            <Maximize2 className="h-3 w-3" />
          )}
          {expanded ? CHROME.collapse : CHROME.expand}
        </button>
      </div>

      {expanded && !isMobile ? (
        <div className="px-3 pb-3 pt-2">
          <Briefing artifact={artifact} />
        </div>
      ) : (
        <InlineBody artifact={artifact} />
      )}

      {expanded && isMobile && (
        <ExpandedOverlay artifact={artifact} onClose={() => setExpanded(false)} />
      )}
    </div>
  )
}

/**
 * The bounded treatment.
 *
 * The tabs are built by walking the projection's axes, which are already in the
 * invariant order, so nothing here can reorder them. The default tab is the
 * lead axis and is set once — a controlled value would re-select the lead every
 * time the artifact re-rendered and take the reader back off the tab they
 * opened.
 */
function InlineBody({ artifact }: { artifact: Artifact }) {
  return (
    <div className="space-y-3 px-3 pb-3 pt-2">
      <PriceZoneBand zone={artifact.priceZone} />

      <Tabs defaultValue={artifact.leadAxis}>
        <TabsList className="h-auto w-full justify-start overflow-x-auto p-0.5">
          {artifact.axes.map((axis) => (
            <TabsTrigger
              key={axis.axis}
              value={axis.axis}
              className="px-2 py-1 text-[11px]"
            >
              {AXIS_LABEL[axis.axis]}
            </TabsTrigger>
          ))}
        </TabsList>

        {artifact.axes.map((axis) => (
          <TabsContent key={axis.axis} value={axis.axis} className="mt-2">
            {/* Bounded, and scrolling inside itself rather than growing the
                transcript. The lead axis is given more of that height, which is
                the other half of what emphasis buys (`docs/specs/0002` §5); the
                bound itself is the artifact's promise that ten of these in one
                Thread stay scrollable. */}
            <div
              className={cn(
                "scrollbar-thin overflow-y-auto pr-1",
                axis.emphasis === "lead" ? "max-h-96" : "max-h-64",
              )}
            >
              <AxisPanel axis={axis} />
            </div>
          </TabsContent>
        ))}
      </Tabs>

      {/* The band is the only graphic here; every other chart the reader might
          want is Stock 360's, and this is the pointer to it. Inline as well as
          expanded, because a reader who never expands still asked the question.
          */}
      <p className="text-[11px]">
        <Link
          href={`/analytics/deep-dive?symbol=${encodeURIComponent(artifact.symbol)}`}
          className="underline underline-offset-2"
        >
          {CHROME.deepDive}
        </Link>
      </p>

      <ArtifactRiskNotice />
    </div>
  )
}


function ExpandedOverlay({
  artifact,
  onClose,
}: {
  artifact: Artifact
  onClose: () => void
}) {
  return (
    <DialogPrimitive.Root open onOpenChange={(next) => !next && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/70" />
        <DialogPrimitive.Content className="fixed inset-0 z-50 overflow-y-auto bg-background p-4">
          <div className="flex items-start justify-between gap-4">
            <DialogPrimitive.Title className="text-sm font-semibold">
              {CHROME.briefing} · {artifact.symbol}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close
              aria-label={CHROME.close}
              className="rounded-md p-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X className="h-4 w-4" />
            </DialogPrimitive.Close>
          </div>
          <DialogPrimitive.Description className="sr-only">
            {artifact.verdictLine ?? artifact.symbol}
          </DialogPrimitive.Description>
          <Briefing artifact={artifact} className="mt-3" />
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
