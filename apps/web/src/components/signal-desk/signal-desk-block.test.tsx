// @vitest-environment jsdom
/**
 * One block, and the promise every block makes about its numbers.
 *
 * A chart is a grid of rectangles with no text in it. The registry's table is a
 * *degradation* — it fires when a version is unknown or a kind is unrenderable
 * — so before this, a chart that drew perfectly left its numbers behind a hover,
 * and a hover does not exist on a touch screen. The disclosure is the route to
 * them that does not depend on something having gone wrong.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { SIGNAL_DESK_COPY } from "@/lib/alpha-desk/copy"
import type { SignalDeskBlock, Frame, Provenance } from "@/lib/alpha-desk/types"

import { SignalDeskBlockView } from "./signal-desk-block"

afterEach(cleanup)

const PROVENANCE: Provenance = {
  source: "vnstock",
  asOf: "2026-08-21T09:00:00+00:00",
  sessionsUsed: 30,
  health: "normal",
  reason: null,
}

const FRAME: Frame = {
  kind: "table",
  columns: ["label", "value", "unit"],
  rows: [["Khối lượng trung bình", 380_000, "shares"]],
  unit: null,
  labels: { label: "Chỉ số", value: "Giá trị", unit: "Đơn vị" },
}

const BLOCK: SignalDeskBlock = {
  widget: "stat_tiles",
  widgetVersion: 1,
  frame: "tiles",
  options: { label: "label", value: "value", unit: "unit" },
}

function draw(block: SignalDeskBlock = BLOCK, frame: Frame | undefined = FRAME) {
  return render(
    <SignalDeskBlockView block={block} frame={frame} provenance={PROVENANCE} />,
  )
}

/** The block with nothing behind it. Spelt out, because passing `undefined`
    for an argument with a default is passing the default. */
function drawWithoutFrame() {
  return render(
    <SignalDeskBlockView block={BLOCK} frame={undefined} provenance={PROVENANCE} />,
  )
}

/**
 * Open the disclosure the way the browser does.
 *
 * Setting `open` and firing `toggle` rather than clicking the summary: the
 * summary's activation behaviour is the browser's, and what this component
 * actually wires is the `toggle` the browser sends afterwards.
 */
function open(container: HTMLElement) {
  const details = container.querySelector("details") as HTMLDetailsElement
  details.open = true
  fireEvent(details, new Event("toggle"))
}

describe("the numbers as a table", () => {
  it("offers the table under a widget that drew perfectly well", () => {
    const { container } = draw()

    expect(screen.getByText("Xem dạng bảng")).toBeInTheDocument()
    // Closed, it costs nothing: a heatmap frame is five hundred cells, and
    // rendering them into a surface nobody opened would be paid for on the
    // panel's first paint.
    expect(screen.queryByRole("table")).toBeNull()

    open(container)

    expect(screen.getByRole("table")).toBeInTheDocument()
    // The frame's own rows, not a second reading of them.
    expect(screen.getAllByText("Khối lượng trung bình")).toHaveLength(2)
  })

  it("makes the wide-frame table a scroll region a keyboard can reach", () => {
    const { container } = draw()
    open(container)

    // Seventeen columns in a four-hundred-pixel panel scroll sideways, and a
    // frame of unbounded length scrolls down inside the same box rather than
    // pushing the blocks under it off the panel. A scroll area reachable only
    // by dragging is one a keyboard cannot reach, on either axis.
    const region = screen.getByRole("region")
    expect(region.getAttribute("tabindex")).toBe("0")
    expect(region.className).toContain("overflow-auto")
    expect(region.className).toContain("max-h-[26rem]")
  })

  it("does not offer a table under the table", () => {
    draw({ ...BLOCK, widget: "data_table" })

    expect(screen.queryByText("Xem dạng bảng")).toBeNull()
  })

  it("does not offer a table under a block that already degraded to one", () => {
    // An unknown version renders as the table and says so; a disclosure beside
    // that note would open a second copy of the same thing.
    draw({ ...BLOCK, widgetVersion: 99 })

    expect(screen.getByText(/Hiển thị dạng bảng/)).toBeInTheDocument()
    expect(screen.queryByText("Xem dạng bảng")).toBeNull()
  })
})

describe("a block with no frame behind it", () => {
  it("says so rather than leaving a gap nobody can see", () => {
    drawWithoutFrame()

    expect(screen.getByText(SIGNAL_DESK_COPY.blockNoData)).toBeInTheDocument()
    expect(screen.queryByText("Xem dạng bảng")).toBeNull()
  })
})

describe("what a block is allowed to say", () => {
  /** Everything the machinery calls things, none of which is a reader's word. */
  const MACHINERY = ["stat_tiles", "data_table", "tiles", "v1", "frame", "widget"]

  it("names no widget, no version and no frame key when it cannot draw", () => {
    // The report this was built from: a reader met "chưa vẽ được bar_series v2"
    // on a product that had promised them an analysis.
    const { container } = render(
      <SignalDeskBlockView
        block={{ ...BLOCK, widget: "stat_tiles", widgetVersion: 99 }}
        frame={FRAME}
        provenance={PROVENANCE}
      />,
    )

    const note = screen.getByText(SIGNAL_DESK_COPY.blockAsTable)
    expect(note).toBeInTheDocument()
    for (const word of MACHINERY) {
      expect(container.textContent).not.toContain(word)
    }
  })

  it("names none of it when there is no frame behind the block either", () => {
    const { container } = drawWithoutFrame()

    for (const word of MACHINERY) {
      expect(container.textContent).not.toContain(word)
    }
  })
})
