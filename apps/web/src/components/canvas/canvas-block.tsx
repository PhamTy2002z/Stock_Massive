"use client"

/**
 * One block: the widget it asked for, or the honest substitute, and a label.
 *
 * `React.memo` on the identity of the block rather than on its contents. A deep
 * comparison of a thirty-by-seventeen matrix runs on every parent render and
 * costs more than the render it is avoiding — the lesson the inventory records
 * from the `isEqual` charts that preceded this. The frame object is immutable
 * once fetched, so reference equality is exactly the right question.
 */

import { memo } from "react"

import type { CanvasBlock, Frame, Provenance } from "@/lib/alpha-desk/types"

import { resolveWidget } from "./widget-registry"

function Block({
  block,
  frame,
  provenance,
}: {
  block: CanvasBlock
  frame: Frame | undefined
  /**
   * Where the numbers came from, handed down rather than looked up.
   *
   * The strip above the blocks is what shows it today; it is on every widget's
   * props because a widget that wants to stamp a date in its own corner should
   * not have to change the contract to get one.
   */
  provenance: Provenance
}) {
  if (frame === undefined) {
    // The server checks that every block names a frame the run produced, so
    // this means the two builds disagree. Said out loud rather than rendered as
    // a gap: a missing block is a hole nobody can see.
    return (
      <p className="text-meta text-muted-foreground">
        Không có dữ liệu cho khối &ldquo;{block.frame}&rdquo;.
      </p>
    )
  }

  const { component: Widget, degraded } = resolveWidget(
    block.widget,
    block.widgetVersion,
    frame.kind,
  )

  return (
    <section>
      <Widget frame={frame} options={block.options} provenance={provenance} />
      {degraded && (
        <p className="mt-1.5 text-meta text-muted-foreground">
          Hiển thị dạng bảng — bản xem này chưa vẽ được {block.widget} v
          {block.widgetVersion}.
        </p>
      )}
    </section>
  )
}

export const CanvasBlockView = memo(
  Block,
  (before, after) =>
    before.block === after.block &&
    before.frame === after.frame &&
    before.provenance === after.provenance,
)
