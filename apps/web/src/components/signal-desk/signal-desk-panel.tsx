"use client"

/**
 * The picture behind an answer, beside the answer.
 *
 * Four things are decided here rather than by the widgets under it.
 *
 * **The skeleton is drawn before the numbers arrive.** The announcement carries
 * `blockCount`, so the panel knows how tall the picture is the instant it hears
 * about one — a box of the right height that fills in, rather than an empty
 * panel that jumps when the fetch lands.
 *
 * **The artifact is fetched once and cached forever.** The freeze lives in
 * `useArtifact`, shared with the chrome above so both read one row under one set
 * of rules.
 *
 * **The provenance strip is not optional chrome.** A reader looking at a
 * heatmap of a fortnight ago has to be told it is a fortnight ago; a picture
 * with no date reads as now. Source, as-of, sessions and health travel together
 * because any one of them alone is a fact nobody can weigh.
 *
 * **A block that cannot be drawn is still a block.** The registry degrades to a
 * table and says so, and the panel renders the degraded block in place rather
 * than dropping it — a missing block is a hole the reader cannot see, where a
 * table with a note is a hole they can.
 *
 * The page margins are the pane's, not this component's: the Signal Desk centres
 * one 1120px column and everything in it — the title, the strip, the blocks —
 * lines up against that single measure.
 */

import { useEffect, useMemo } from "react"

import { FailureState } from "@/components/ui/failure-state"
import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import { describeFailure } from "@/lib/failure"
import type { SignalDeskBlock, Frame } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"

import { SignalDeskBlockView } from "./signal-desk-block"
import { ProvenanceStrip } from "./provenance-strip"
import { useArtifact } from "./use-artifact"

export function SignalDeskPanel({
  artifactId,
  title,
  blockCount,
  /**
   * Frozen while the reader drags the seam.
   *
   * A chart measured on every pointer move re-lays out on every frame, and the
   * drag stutters. The width is held still until the handle is released; the
   * charts re-measure once, then.
   */
  frozen = false,
  /**
   * The name the row turned out to carry.
   *
   * A tab opened out of the transcript has only an id to go on — the card there
   * hands over which picture, not what it is called — so the strip would label
   * it generically forever. This is how it learns, once, from the fetch that was
   * happening anyway.
   */
  onTitle,
}: {
  artifactId: string | null
  title?: string
  blockCount?: number
  frozen?: boolean
  onTitle?: (artifactId: string, title: string) => void
}) {
  const artifact = useArtifact(artifactId)

  const frames: Record<string, Frame> = useMemo(
    () => artifact.data?.frames ?? {},
    [artifact.data],
  )

  const resolvedTitle = artifact.data?.signal_desk_spec?.title
  useEffect(() => {
    if (artifactId === null || onTitle === undefined) return
    if (resolvedTitle === undefined || resolvedTitle === "") return
    onTitle(artifactId, resolvedTitle)
  }, [artifactId, resolvedTitle, onTitle])

  if (artifactId === null) {
    return <p className="text-meta text-muted-foreground">{SIGNAL_DESK_COPY.noDeskView}</p>
  }

  // Two failures, and only one of them is worth a button.
  //
  // `useArtifact` does not retry, deliberately: the failure this route was
  // built expecting is a 404, and asking twice only delays the one true
  // answer. That reasoning does not cover a dropped connection, and treating
  // both as the same dead end left the desk blank until a full page reload —
  // for a row that is frozen server-side and would have arrived on a second
  // request.
  //
  // Which of the two it is, and what the reader can do about it, is decided by
  // `describeFailure` along with every other failure in the product. The one
  // thing overridden is the sentence for a 404, because this surface knows
  // something the classifier cannot: an artifact id that resolves to nothing is
  // almost always another Thread's, not a deleted one.
  if (artifact.isError) {
    const classified = describeFailure(artifact.error)
    const failure =
      classified.kind === "not_found"
        ? { ...classified, detail: SIGNAL_DESK_COPY.unreachable }
        : classified

    return (
      <FailureState
        failure={failure}
        density="inline"
        onRetry={() => void artifact.refetch()}
      />
    )
  }

  const spec = artifact.data?.signal_desk_spec
  const blocks: SignalDeskBlock[] = spec?.blocks ?? []

  return (
    <div className={cn(frozen && "pointer-events-none")}>
      <h3 className="text-pretty text-[1.32rem] font-medium tracking-[-0.015em] text-ink-1">
        {spec?.title ?? title ?? SIGNAL_DESK_COPY.name}
      </h3>

      {artifact.data !== undefined && (
        <ProvenanceStrip provenance={artifact.data.provenance} />
      )}

      {/* Keyed on whether the numbers have arrived, so the blocks fade in over
          where the skeleton stood instead of replacing it between two frames. */}
      <div
        key={artifact.data === undefined ? "skeleton" : "blocks"}
        className="mt-3.5 space-y-3.5 motion-safe:animate-vg-fade-in"
      >
        {artifact.data === undefined ? (
          Array.from({ length: Math.max(1, blockCount ?? 1) }).map((_, index) => (
            <Skeleton key={index} />
          ))
        ) : blocks.length === 0 ? (
          // Said rather than left blank. A fetch that succeeded and carried no
          // block is the one failure that looks exactly like the skeleton
          // having never resolved, and the reader cannot tell those apart from
          // the outside.
          <p className="text-meta text-muted-foreground">{SIGNAL_DESK_COPY.noBlocks}</p>
        ) : (
          blocks.map((block, index) => (
            <SignalDeskBlockView
              key={`${block.widget}-${block.frame}-${index}`}
              block={block}
              frame={frames[block.frame]}
              provenance={artifact.data.provenance}
            />
          ))
        )}
      </div>
    </div>
  )
}

/**
 * One block's worth of space, held while the numbers are on their way.
 *
 * A fixed height rather than a measured one: the panel does not know how tall
 * this particular chart will be, and a box that is roughly right and does not
 * move beats a box that is exactly right one frame later.
 */
function Skeleton() {
  return (
    <div
      aria-hidden
      className="h-32 animate-pulse rounded-xl border border-hairline bg-surface-raised motion-reduce:animate-none"
    />
  )
}
