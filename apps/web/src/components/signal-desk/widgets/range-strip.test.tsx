// @vitest-environment jsdom
/**
 * The strip, and the three things it exists to get right.
 *
 * **The mark sits where the numbers put it.** The whole content of this widget
 * is one position, so a marker that drifted would be the widget being wrong
 * about the only thing it says.
 *
 * **The band is drawn only when it was measured.** A shaded region with no
 * numbers behind it is a claim about price structure that nothing computed.
 *
 * **The picture is not the only way to read it.** The prices are printed under
 * the track and the whole reading is the image's label, so a reader who cannot
 * see the strip is not told "biểu đồ" and left there.
 *
 * The positions below are read as percentages of the track rather than as user
 * units of a `viewBox`, which is the fix this widget carries: the strip is laid
 * out at the panel's own width instead of being one drawing stretched to it, so
 * the two-pixel rule is two pixels wide however wide the panel is.
 */

import { cleanup, render } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { Frame, Provenance } from "@/lib/alpha-desk/types"

import { RangeStripWidget } from "./range-strip"

afterEach(cleanup)

const PROVENANCE: Provenance = {
  source: "vnstock",
  asOf: "2026-08-21T09:00:00+00:00",
  sessionsUsed: 250,
  health: "normal",
  reason: null,
}

/** The condition review's own frame: a 52-week band with a cluster inside it. */
const FRAME: Frame = {
  kind: "table",
  columns: ["low", "high", "current", "percentile", "zone_low", "zone_high"],
  rows: [[67_900, 80_100, 71_350, 28.28, 71_000, 71_600]],
  unit: "VND",
  labels: {
    low: "Đáy 52 tuần",
    high: "Đỉnh 52 tuần",
    current: "Giá đóng cửa gần nhất",
    percentile: "Vị thế trong dải (%)",
    zone_low: "Đáy vùng giá đóng cửa tập trung",
    zone_high: "Đỉnh vùng giá đóng cửa tập trung",
  },
}

const OPTIONS = {
  low: "low",
  high: "high",
  current: "current",
  percentile: "percentile",
  bandLow: "zone_low",
  bandHigh: "zone_high",
  bandLabel: "Vùng giá đóng cửa tập trung 60 phiên",
}

function draw(frame: Frame = FRAME, options: Record<string, unknown> = OPTIONS) {
  return render(
    <RangeStripWidget frame={frame} options={options} provenance={PROVENANCE} />,
  )
}

/** One part of the strip, by the name it carries for exactly this purpose. */
function part(container: HTMLElement, name: string): HTMLElement | null {
  return container.querySelector(`[data-part="${name}"]`)
}

/** A percentage style as the number it holds. */
function percent(node: HTMLElement | null, property: "left" | "width"): number {
  return Number.parseFloat(node?.style[property] ?? "")
}

describe("the mark", () => {
  it("sits at the fraction of the band the numbers say", () => {
    const { container } = draw()

    // (71.350 - 67.900) / (80.100 - 67.900) = 28,28% of the track.
    expect(percent(part(container, "marker"), "left")).toBeCloseTo(28.28, 1)
  })

  it("stays inside the track when the value sits on an edge", () => {
    const { container } = draw({ ...FRAME, rows: [[100, 200, 200, 100]] })

    expect(percent(part(container, "marker"), "left")).toBe(100)
  })

  it("is drawn at a fixed thickness rather than one that grows with the panel", () => {
    const { container } = draw()

    // The whole claim of this widget is one position, and a rule that widened
    // with the panel would blur the position it claims to be precise about.
    // `w-0.5` is two pixels at every width, where the old `viewBox` stretched.
    const marker = part(container, "marker")
    expect(marker?.className).toContain("w-0.5")
    expect(container.querySelector("[preserveAspectRatio]")).toBeNull()
  })
})

describe("the band inside the band", () => {
  it("is shaded across the fractions the cluster spans", () => {
    const { container } = draw()

    // 71.000 and 71.600 against a band of 67.900–80.100.
    const band = part(container, "band")
    expect(percent(band, "left")).toBeCloseTo(25.41, 1)
    expect(percent(band, "width")).toBeCloseTo(4.92, 1)
  })

  it("is not drawn at all when the frame carries no cluster", () => {
    const { container } = draw({
      ...FRAME,
      columns: ["low", "high", "current"],
      rows: [[67_900, 80_100, 71_350]],
    })

    expect(part(container, "band")).toBeNull()
    expect(container.textContent).not.toContain("Vùng giá")
  })
})

describe("reading it without seeing it", () => {
  it("labels the image with the whole reading rather than with its kind", () => {
    const { container } = draw()

    const label =
      container.querySelector('[role="img"]')?.getAttribute("aria-label") ?? ""
    expect(label).toContain("71,4\u00a0nghìn đồng")
    expect(label).toContain("67,9–80,1")
    expect(label).toContain("28,3% của dải")
    expect(label).toContain("Vùng giá đóng cửa tập trung 60 phiên")
  })

  it("prints the three prices under the track", () => {
    const { container } = draw()

    expect(container.textContent).toContain("nghìn đồng")
    expect(container.textContent).toContain("67,9")
    expect(container.textContent).toContain("71,4")
    expect(container.textContent).toContain("80,1")
    expect(container.textContent).toContain("(28,3% dải)")
  })

  it("says the numbers are short rather than drawing an empty ruler", () => {
    const { container } = draw({ ...FRAME, rows: [] })

    expect(part(container, "track")).toBeNull()
    expect(container.textContent).toContain("Chưa đủ số")
  })

  it("refuses a band with no width, where every position would be the same", () => {
    const { container } = draw({ ...FRAME, rows: [[100, 100, 100, 50]] })

    expect(part(container, "track")).toBeNull()
  })
})

describe("a frame nobody shaped for this widget", () => {
  it("reads the first three columns when the server sent no options", () => {
    // What `render_signal_desk` composes: a frame a Study did not shape for this
    // widget, and no column names it recognises.
    const { container } = draw(
      {
        ...FRAME,
        columns: ["a", "b", "c"],
        rows: [[10, 20, 15]],
        labels: { a: "A", b: "B", c: "C" },
      },
      {},
    )

    expect(percent(part(container, "marker"), "left")).toBeCloseTo(50, 1)
  })
})

describe("both themes", () => {
  it("paints with tokens only, which is what makes the dark and light grounds work", () => {
    const { container } = draw()

    const painted = [...container.querySelectorAll("polygon, [style]")].flatMap(
      (node) => [
        node.getAttribute("fill"),
        node.getAttribute("stroke"),
        // Only the paint, not the geometry: `left` is a percentage and would
        // never be a token.
        (node as HTMLElement).style?.background ?? null,
      ],
    )

    for (const value of painted) {
      if (value === null || value === "none" || value === "") continue
      expect(value, `${value} is not a token`).toMatch(/var\(--/)
    }
  })

  it("borrows neither the brand amber for the band nor a market colour for the track", () => {
    const { container } = draw()

    // The mark is the one focus this strip is allowed: it is the single number
    // the reader came for. Everything under it is the neutral series.
    expect(part(container, "marker")?.style.background).toContain("--widget-focus")
    expect(part(container, "band")?.style.background).toContain("--widget-series")
    expect(part(container, "track")?.style.background).toContain("--widget-track")
  })
})
