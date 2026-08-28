// @vitest-environment jsdom
/**
 * The heatmap, and the two things it exists to get right.
 *
 * **A hole is not a zero.** Real sessions are missing buckets — a HOSE symbol
 * has no 09:00 at all — and every charting library treats an absent value as
 * nought. Nought here is a different and false claim: that the quarter hour
 * existed and nobody traded in it. So the cell is drawn as a hole and says so
 * to a screen reader.
 *
 * **Every column is named on the page.** Labelling every other one left the odd
 * buckets identifiable only by counting across from a neighbour, and the
 * `<title>` that was supposed to cover them is a hover, which a touch screen
 * does not have.
 *
 * **Every colour resolves through a token.** The app opens dark and the reader
 * can switch to light, and a literal `#888` is legible in one of them. A DOM
 * test cannot measure contrast, but it can prove the mechanism that makes both
 * themes work: nothing here paints with anything but a CSS variable.
 */

import { cleanup, render } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { Frame, Provenance } from "@/lib/alpha-desk/types"

import { SessionHeatmapWidget } from "./session-heatmap"

afterEach(cleanup)

const PROVENANCE: Provenance = {
  source: "vnstock",
  asOf: "2026-08-21T09:00:00+00:00",
  sessionsUsed: 2,
  health: "normal",
  reason: null,
}

/** Two sessions across three buckets, one of them missing on the first day. */
const FRAME: Frame = {
  kind: "matrix",
  columns: ["session", "09:00", "09:15", "14:45"],
  rows: [
    ["2026-08-20", null, 0.2, 0.8],
    ["2026-08-21", 0.1, 0.3, 0.6],
  ],
  unit: "share",
  labels: {
    session: "Phiên",
    "09:00": "09:00",
    "09:15": "09:15",
    "14:45": "14:45",
  },
}

function draw(frame: Frame = FRAME) {
  return render(
    <SessionHeatmapWidget
      frame={frame}
      options={{ rowKey: "session" }}
      provenance={PROVENANCE}
    />,
  )
}

describe("the grid", () => {
  it("draws one cell per session per bucket, and no cell for the row label", () => {
    const { container } = draw()

    // Two sessions × three buckets. The `session` column names the row and is
    // not a bucket, which is the one arithmetic error this widget can make.
    expect(container.querySelectorAll("rect")).toHaveLength(6)
  })

  it("draws a missing bucket as a hole and says so, rather than as nothing traded", () => {
    const { container } = draw()

    const titles = [...container.querySelectorAll("title")].map((node) => node.textContent)
    expect(titles).toContain("2026-08-20 · 09:00: không có dữ liệu")
    // And it is drawn differently: a dashed outline over the sunken surface, so
    // a reader sees the hole rather than a very quiet bucket.
    const hole = container.querySelectorAll("rect")[0]
    expect(hole.getAttribute("fill")).toBe("hsl(var(--surface-sunken))")
    expect(hole.getAttribute("stroke-dasharray")).toBe("1 1")
  })

  it("bands a cell against its own session, so a quiet day reads like a busy one", () => {
    const { container } = draw()

    const cells = [...container.querySelectorAll("rect")]
    // The busiest bucket of each session lands in the top band, whatever the
    // session's own total was: 0.8 of one day and 0.6 of the next.
    const busiestOfDayOne = cells[2].getAttribute("fill")
    const busiestOfDayTwo = cells[5].getAttribute("fill")
    expect(busiestOfDayOne).toBe(busiestOfDayTwo)
  })

  it("names every bucket on the page, not every other one", () => {
    const { container } = draw()

    const drawn = [...container.querySelectorAll("text")].map((node) => node.textContent)
    for (const bucket of ["09:00", "09:15", "14:45"]) {
      expect(drawn, `${bucket} has no label`).toContain(bucket)
    }
  })

  it("stands the bucket labels on end so none of them runs past the edge", () => {
    const { container } = draw()

    // A quarter turn is what buys seventeen four-character labels room in
    // fourteen pixels apiece; flat, the last one overran the drawing's width
    // and arrived clipped mid-label.
    const label = [...container.querySelectorAll("text")].find(
      (node) => node.textContent === "14:45",
    )
    expect(label?.getAttribute("transform")).toMatch(/^rotate\(-90 /)

    const svg = container.querySelector("svg")
    const width = Number(svg?.getAttribute("width"))
    const last = Number(container.querySelectorAll("rect")[2].getAttribute("x"))
    expect(last).toBeLessThan(width)
  })

  it("says the window is too thin rather than drawing an empty grid", () => {
    const { container } = draw({ ...FRAME, rows: [] })

    expect(container.querySelector("svg")).toBeNull()
    expect(container.textContent).toContain("Chưa đủ phiên")
  })
})

describe("both themes", () => {
  it("paints with tokens only, which is what makes the dark and light grounds work", () => {
    const { container } = draw()

    const painted = [...container.querySelectorAll("rect, [style]")].flatMap((node) => [
      node.getAttribute("fill"),
      node.getAttribute("stroke"),
      node.getAttribute("style"),
    ])

    for (const value of painted) {
      if (value === null || value === "none" || value === "") continue
      expect(value, `${value} is not a token`).toMatch(/var\(--/)
    }
  })

  it("climbs a neutral series rather than the brand accent", () => {
    const { container } = draw()

    // The ladder used to be four opacities of the app's lead chart colour,
    // which is the brand amber byte for byte — a busy quarter hour drawn in the
    // colour reserved for the one control a view is allowed.
    const fills = [...container.querySelectorAll("rect")]
      .map((node) => node.getAttribute("fill") ?? "")
      .filter((fill) => !fill.includes("surface-sunken"))

    expect(fills.length).toBeGreaterThan(0)
    for (const fill of fills) {
      expect(fill, `${fill} is not the neutral series`).toContain("--widget-series")
    }
  })
})
