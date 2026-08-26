"use client"

/**
 * The line under an answer that says there is a picture, and opens it.
 *
 * **The transcript stays text-first.** A canvas is four blocks and a heatmap;
 * inlined under every answer it would turn a conversation into a dashboard the
 * reader has to scroll past to find the next sentence. So the transcript gets a
 * card and the panel gets the picture — the reader chooses when to look.
 *
 * The same shape as `SourcePill` beside it, deliberately: both answer "what is
 * this answer resting on", and two different affordances for one question would
 * make the pair read as two unrelated features.
 */

import { ChartNoAxesColumn } from "lucide-react"

import type { CanvasAnnouncement } from "@/lib/alpha-desk/types"

export function CanvasCard({
  canvases,
  onOpen,
}: {
  canvases: CanvasAnnouncement[]
  onOpen: (artifactId: string) => void
}) {
  if (canvases.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1.5">
      {canvases.map((canvas) => (
        <button
          key={canvas.artifactId}
          type="button"
          onClick={() => onOpen(canvas.artifactId)}
          className="group inline-flex max-w-full items-center gap-1.5 rounded-full border border-hairline bg-surface-sunken px-3 py-1 text-meta text-muted-foreground transition-colors hover:border-border hover:text-ink-2"
        >
          <ChartNoAxesColumn className="size-3.5 shrink-0" aria-hidden />
          <span className="truncate">{canvas.title}</span>
          <span className="shrink-0 text-ink-5 group-hover:text-ink-4">
            {/* How many blocks are waiting. A picture is worth opening for a
                reader who can see it is more than one chart. */}
            {canvas.blockCount > 0 ? `${canvas.blockCount} khối` : "mở"}
          </span>
        </button>
      ))}
    </div>
  )
}
