"use client"

/**
 * One block: the widget it asked for, or the honest substitute, and a label.
 *
 * `React.memo` on the identity of the block rather than on its contents. A deep
 * comparison of a thirty-by-seventeen matrix runs on every parent render and
 * costs more than the render it is avoiding — the lesson the inventory records
 * from the `isEqual` charts that preceded this. The frame object is immutable
 * once fetched, so reference equality is exactly the right question.
 *
 * **Every block's numbers are reachable as a table, and not only when something
 * broke.** The registry's fallback is a *degradation* — it fires when a version
 * is unknown or a kind is unrenderable — so a chart that draws perfectly used to
 * leave its numbers behind a hover, and a hover does not exist on a touch
 * screen. The disclosure under each block renders the same frame through the
 * same `data_table` the fallback uses. It costs one line of chrome, and it is
 * the only route to the numbers a reader who cannot see the picture has.
 */

import { memo, useState } from "react"
import { ErrorBoundary } from "react-error-boundary"

import type { SignalDeskBlock, Frame, Provenance } from "@/lib/alpha-desk/types"

import { FALLBACK, resolveWidget } from "./widget-registry"
import { DataTableWidget } from "./widgets/data-table"

function Block({
  block,
  frame,
  provenance,
}: {
  block: SignalDeskBlock
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

  // A block that already *is* the table needs no way to see the table.
  const drawn = !degraded && block.widget !== FALLBACK.widget

  if (degraded) {
    return (
      <section>
        <Degraded frame={frame} options={block.options} provenance={provenance}>
          Hiển thị dạng bảng — bản xem này chưa vẽ được {block.widget} v
          {block.widgetVersion}.
        </Degraded>
      </section>
    )
  }

  return (
    <section>
      {/*
        A widget that throws takes the table's place, not the panel's.

        The registry degrades on what it can see before rendering — an unknown
        version, a kind the widget does not draw. What it cannot see is a frame
        that satisfies the contract and still breaks the chart runtime: a
        domain the scale cannot invert, a path with no finite point in it. That
        throw unmounts every ancestor up to the nearest boundary, so without
        one here a single unlucky block blanks the whole desk — and takes the
        answer beside it. The same numbers as a table is the honest floor, and
        it is already the fallback this file was built around.

        Keyed on the frame so a later artifact gets a fresh attempt rather than
        inheriting the previous one's caught error.
      */}
      <ErrorBoundary
        resetKeys={[frame]}
        fallbackRender={() => (
          <Degraded frame={frame} options={block.options} provenance={provenance}>
            Hiển thị dạng bảng — không vẽ được {block.widget} với dữ liệu của
            bảng này.
          </Degraded>
        )}
      >
        <Widget frame={frame} options={block.options} provenance={provenance} />
      </ErrorBoundary>
      {drawn && <FrameTable frame={frame} provenance={provenance} />}
    </section>
  )
}

/**
 * The numbers without the picture, and the reason the picture is missing.
 *
 * One component for both routes to it — the version this build cannot draw and
 * the frame that broke the one it has — so the two never drift into looking
 * like different failures to a reader. The note is never omitted: a table
 * appearing where a chart was asked for is a hole the reader can see, and the
 * sentence is what tells them it is a hole rather than the design.
 */
function Degraded({
  frame,
  options,
  provenance,
  children,
}: {
  frame: Frame
  options: Record<string, unknown>
  provenance: Provenance
  children: React.ReactNode
}) {
  return (
    <>
      <DataTableWidget frame={frame} options={options} provenance={provenance} />
      <p className="mt-1.5 text-meta text-muted-foreground">{children}</p>
    </>
  )
}

/**
 * The same frame as numbers, on request.
 *
 * Mounted only once it is opened. A heatmap frame is thirty rows of eighteen
 * cells, and rendering five hundred of them into a closed disclosure would put
 * the cost of a surface nobody asked for on the panel's first paint.
 */
function FrameTable({ frame, provenance }: { frame: Frame; provenance: Provenance }) {
  const [open, setOpen] = useState(false)

  return (
    <details
      className="mt-1.5"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer text-meta text-muted-foreground hover:text-ink-2">
        Xem dạng bảng
      </summary>
      {open && (
        <div className="mt-1.5">
          <DataTableWidget frame={frame} options={{}} provenance={provenance} />
        </div>
      )}
    </details>
  )
}

export const SignalDeskBlockView = memo(
  Block,
  (before, after) =>
    before.block === after.block &&
    before.frame === after.frame &&
    before.provenance === after.provenance,
)
