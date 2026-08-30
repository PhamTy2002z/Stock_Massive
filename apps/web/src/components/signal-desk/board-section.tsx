"use client"

/**
 * One idea of a board: a heading, and the blocks under it on the server's grid.
 *
 * The spans arrive decided. What this adds is the one thing the server could not
 * see — a panel too narrow for thirds — and it adds it through `layout.ts`,
 * which mirrors the server's own table rather than inventing a second one.
 *
 * A caption is drawn here rather than by the widget registry, because it is not
 * a picture of a frame: it is a sentence whose figures were resolved out of
 * several. The registry draws frames.
 */

import type { BoardBlock, BoardSection as Section, Frame, Provenance } from "@/lib/alpha-desk/types"

import { CaptionWidget } from "./widgets/caption"
import { gridColumn } from "./layout"
import { SignalDeskBlockView } from "./signal-desk-block"
import { SourceBadge } from "./source-badge"

export function BoardSectionView({
  section,
  frames,
  provenance,
  width,
}: {
  section: Section
  frames: Record<string, Frame>
  provenance: Provenance
  width: number
}) {
  return (
    <section className="mt-4 first:mt-0">
      {section.heading !== null && section.heading !== "" && (
        <h4 className="mb-2.5 text-meta font-semibold uppercase tracking-[0.09em] text-muted-foreground">
          {section.heading}
        </h4>
      )}
      <div className="grid grid-cols-12 gap-3">
        {section.blocks.map((block, index) => (
          <div
            key={index}
            style={{ gridColumn: gridColumn(block.span, width) }}
            /* Every block sits on its own card. A picture and the caption under
               it are two claims about the same numbers, and a reader separates
               them by the edge between them rather than by the gap. */
            className="min-w-0 rounded-[13px] border border-hairline bg-surface-sunken p-4"
          >
            <BlockView block={block} frames={frames} provenance={provenance} />
          </div>
        ))}
      </div>
    </section>
  )
}

function BlockView({
  block,
  frames,
  provenance,
}: {
  block: BoardBlock
  frames: Record<string, Frame>
  provenance: Provenance
}) {
  if (block.kind === "caption") {
    return <CaptionWidget caption={block} />
  }
  return (
    <>
      <SignalDeskBlockView
        block={{
          widget: block.widget,
          widgetVersion: block.widgetVersion,
          frame: block.frame,
          options: block.options,
        }}
        frame={frames[block.frame]}
        provenance={provenance}
      />
      {(block.source !== "store" || block.downgraded !== null) && (
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <SourceBadge source={block.source} />
          {block.downgraded !== null && (
            // Said out loud, never swallowed. A picture that turned into
            // numbers because no rule matched is a hole the reader can see;
            // silently drawing the table would be one they cannot.
            <span className="text-meta text-muted-foreground">{block.downgraded}</span>
          )}
        </div>
      )}
    </>
  )
}
