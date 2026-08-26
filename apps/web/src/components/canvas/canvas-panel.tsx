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
 * **The artifact is fetched once and cached forever.** The row is immutable by
 * design: it is written once and re-opening a Thread renders what was frozen.
 * `staleTime: Infinity` is not a performance choice, it is the freeze — a
 * refetch could only ever return the same bytes, and treating the resource as
 * stale would invite a future change to ask the store for a fresher slice.
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
 */

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"

import { fetchArtifact } from "@/lib/alpha-desk/api"
import type { CanvasBlock, Frame } from "@/lib/alpha-desk/types"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"

import { CanvasBlockView } from "./canvas-block"
import { ProvenanceStrip } from "./provenance-strip"

export function CanvasPanel({
  artifactId,
  title,
  blockCount,
  /**
   * Frozen while the reader drags the panel's edge.
   *
   * A chart measured on every pointer move re-lays out on every frame, and the
   * drag stutters. The width is held still until the handle is released; the
   * charts re-measure once, then.
   */
  frozen = false,
}: {
  artifactId: string | null
  title?: string
  blockCount?: number
  frozen?: boolean
}) {
  const artifact = useQuery({
    queryKey: queryKeys.artifact(artifactId ?? ""),
    queryFn: () => fetchArtifact(artifactId as string),
    enabled: artifactId !== null,
    staleTime: Infinity,
    gcTime: Infinity,
    // Nothing about an immutable row changes because a tab regained focus.
    refetchOnWindowFocus: false,
    // No retry. The failure this route actually has is a 404 — an artifact
    // belonging to another Thread — and retrying it asks the same question
    // twice before telling the reader the one true answer.
    retry: false,
  })

  const frames: Record<string, Frame> = useMemo(
    () => artifact.data?.frames ?? {},
    [artifact.data],
  )

  if (artifactId === null) {
    return (
      <p className="px-1 py-2 text-meta text-muted-foreground">
        Chưa có phân tích nào được vẽ trong hội thoại này.
      </p>
    )
  }

  if (artifact.isError) {
    return (
      <div className="px-1 py-2">
        <p className="text-meta text-muted-foreground">
          Không mở được phân tích này. Nó có thể thuộc một hội thoại khác.
        </p>
      </div>
    )
  }

  const spec = artifact.data?.canvas_spec
  const blocks: CanvasBlock[] = spec?.blocks ?? []

  return (
    <div className={cn("px-3 pb-6 pt-3", frozen && "pointer-events-none")}>
      <h3 className="text-pretty text-sm font-medium text-ink-1">
        {spec?.title ?? title ?? "Phân tích"}
      </h3>

      {artifact.data !== undefined && (
        <ProvenanceStrip provenance={artifact.data.provenance} />
      )}

      <div className="mt-3 space-y-4">
        {artifact.data === undefined
          ? Array.from({ length: Math.max(1, blockCount ?? 1) }).map((_, index) => (
              <Skeleton key={index} />
            ))
          : blocks.map((block, index) => (
              <CanvasBlockView
                key={`${block.widget}-${block.frame}-${index}`}
                block={block}
                frame={frames[block.frame]}
                provenance={artifact.data.provenance}
              />
            ))}
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
      className="h-32 animate-pulse rounded-lg border border-hairline bg-surface-sunken"
    />
  )
}
