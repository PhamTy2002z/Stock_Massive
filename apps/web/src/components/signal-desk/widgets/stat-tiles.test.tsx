// @vitest-environment jsdom
/**
 * The lead numbers, and the rule that keeps a tile in one language.
 *
 * The value and the unit are two cells of the frame and two spans on the tile,
 * so exactly one of them may speak the magnitude. The real case: an average of
 * 380.000 with a unit of `shares` rendered as "380,00 ng shares" — the axis
 * shorthand ran straight into an English unit, and "ng" beside another word
 * reads as a unit itself.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { Frame, Provenance } from "@/lib/alpha-desk/types"

import { StatTilesWidget } from "./stat-tiles"

afterEach(cleanup)

const PROVENANCE: Provenance = {
  source: "vnstock",
  asOf: "2026-08-21T09:00:00+00:00",
  sessionsUsed: 30,
  health: "normal",
  reason: null,
}

/** The intraday profile's own tiles, verbatim. */
const FRAME: Frame = {
  kind: "table",
  columns: ["label", "value", "unit"],
  rows: [
    ["Khung giờ đỉnh", "14:45", null],
    ["Tỷ trọng thanh khoản", 19.38, "%"],
    ["Khối lượng trung bình", 380_000, "shares"],
    ["Số phiên lặp lại", "21/30", "phiên"],
  ],
  unit: null,
  labels: { label: "Chỉ số", value: "Giá trị", unit: "Đơn vị" },
}

function draw(frame: Frame = FRAME) {
  return render(
    <StatTilesWidget
      frame={frame}
      options={{ label: "label", value: "value", unit: "unit" }}
      provenance={PROVENANCE}
    />,
  )
}

describe("a tile's reading", () => {
  it("spells the magnitude out and says the unit in Vietnamese", () => {
    const { container } = draw()

    expect(container.textContent).toContain("380nghìn cp")
    expect(container.textContent).toContain("cp")
    expect(container.textContent).not.toContain("shares")
    expect(container.textContent).not.toContain("ng shares")
  })

  it("leaves a unit a Study already wrote in Vietnamese alone", () => {
    const { container } = draw()

    expect(container.textContent).toContain("phiên")
    expect(container.textContent).toContain("19,4%")
  })

  it("prints a label the Study sent as a value, without formatting it as a number", () => {
    draw()

    expect(screen.getByText("14:45")).toBeInTheDocument()
  })

  it("prints an em dash where nothing was measured, never a nought", () => {
    const { container } = draw({ ...FRAME, rows: [["Chỉ số", null, "cp"]] })

    expect(container.textContent).toContain("—")
    expect(container.textContent).not.toContain("0 cp")
  })

  it("says there is nothing to lead with rather than drawing empty boxes", () => {
    const { container } = draw({ ...FRAME, rows: [] })

    expect(container.querySelector("dl")).toBeNull()
    expect(container.textContent).toContain("Chưa có số dẫn dắt")
  })
})

describe("how many tiles fit", () => {
  it("counts columns from the grid rather than from the viewport", () => {
    const { container } = draw()

    // The inspector is a column a reader drags, so a breakpoint measures the
    // wrong box: at 420 pixels of panel on a wide screen every breakpoint says
    // "wide" and the tiles stay two across whatever the panel is doing.
    const grid = container.querySelector("dl")
    expect(grid?.className).toContain("auto-fit")
    expect(grid?.className).not.toContain("grid-cols-2")
  })
})
