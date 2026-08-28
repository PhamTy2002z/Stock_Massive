// @vitest-environment jsdom
/**
 * The bar chart, and the two things that make it say more than its headline.
 *
 * **The ceiling.** A liquidity profile is one dominant bucket and thirty small
 * ones. Scaled to the dominant bucket the thirty are a rule along the baseline:
 * arithmetically correct, and a picture that repeats the sentence above it
 * rather than adding to it. The ceiling is derived from the distribution, so it
 * appears where there is an outlier and stays out of the way where there is not
 * — a flat series must never be rescaled, because nothing about it is hidden.
 *
 * **The focus.** Exactly one bar carries the accent, and it is the bar the
 * answer is about. A whole series in the accent is the chart claiming to be a
 * control, which is the one thing the brand's amber is reserved for.
 */

import { cleanup, render } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { Frame, Provenance } from "@/lib/alpha-desk/types"

import { BarSeriesWidget, plotCeiling } from "./bar-series"

afterEach(cleanup)

const PROVENANCE: Provenance = {
  source: "vnstock",
  asOf: "2026-08-21T09:00:00+00:00",
  sessionsUsed: 30,
  health: "normal",
  reason: null,
}

/** The real shape: one peak and a tail nobody can compare against it. */
const SKEWED = [0.19, ...Array.from({ length: 29 }, () => 0.015)]

describe("how far up the plot goes", () => {
  it("stops below a lone peak, so the tail is a comparison rather than a baseline", () => {
    const ceiling = plotCeiling(SKEWED)

    expect(ceiling).not.toBeNull()
    expect(ceiling as number).toBeLessThan(0.19)
    // And well above the tail, so the tail has most of the plot to itself.
    expect(ceiling as number).toBeGreaterThan(0.015)
  })

  it("leaves a flat series exactly as it is, because nothing in it is hidden", () => {
    const flat = [0.3, 0.31, 0.33, 0.34, 0.35]

    // The percentile of a flat series is its own maximum, so the rule that caps
    // an outlier has nothing to cap here. That is the point of taking the `min`
    // with the maximum rather than trusting the percentile alone.
    expect(plotCeiling(flat)).toBe(0.35)
  })

  it("lets a series that crosses zero scale itself", () => {
    // A ceiling would truncate one end of a comparison the reader makes across
    // the axis, which is a different chart from the one the Study asked for.
    expect(plotCeiling([-4, 1, 2, 30])).toBeNull()
  })

  it("lets a series of nothing but nought scale itself", () => {
    expect(plotCeiling([0, 0, 0])).toBeNull()
    expect(plotCeiling([])).toBeNull()
  })

  it("never returns a ceiling above the tallest bar", () => {
    for (const values of [SKEWED, [1, 2, 3], [5, 5, 5, 5, 9]]) {
      expect(plotCeiling(values) as number).toBeLessThanOrEqual(Math.max(...values))
    }
  })
})

describe("what is drawn", () => {
  beforeEach(() => {
    // ResizeObserver is what recharts measures its container with, and jsdom
    // has none. The assertions here are about the words on the page.
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
  })

  afterEach(() => vi.unstubAllGlobals())

  function frame(values: number[]): Frame {
    return {
      kind: "series",
      columns: ["bucket", "share"],
      rows: values.map((value, index) => [`09:${String(index).padStart(2, "0")}`, value]),
      unit: "share",
      labels: { bucket: "Khung giờ", share: "Tỷ trọng trong phiên" },
    }
  }

  function draw(values: number[]) {
    return render(
      <BarSeriesWidget
        frame={frame(values)}
        options={{ x: "bucket", y: "share", yFormat: "percent" }}
        provenance={PROVENANCE}
      />,
    )
  }

  it("says where the axis stops and how many bars were cut there", () => {
    const { container } = draw(SKEWED)

    // A cut nobody is told about is the chart quietly redrawing the numbers.
    expect(container.textContent).toContain("Trục dừng ở")
    expect(container.textContent).toContain("1 cột cao hơn")
  })

  it("says nothing about a ceiling when it did not move one", () => {
    const { container } = draw([0.3, 0.31, 0.33, 0.34, 0.35])

    expect(container.textContent).not.toContain("Trục dừng")
  })

  it("accents one bar, never the series, even where every bar is the same", () => {
    const { container } = draw([0.2, 0.2, 0.2, 0.2])

    // A series with no peak has nothing for the accent to point at, and a
    // series painted entirely in it is the chart claiming to be a control.
    const accented = [...container.querySelectorAll("path, rect")].filter((node) =>
      (node.getAttribute("fill") ?? "").includes("--widget-focus"),
    )
    expect(accented.length).toBeLessThanOrEqual(1)
  })

  it("says there is nothing to draw rather than drawing an empty plot", () => {
    const { container } = render(
      <BarSeriesWidget
        frame={{ ...frame([]), rows: [["09:00", null]] }}
        options={{ x: "bucket", y: "share" }}
        provenance={PROVENANCE}
      />,
    )

    expect(container.textContent).toContain("Không có điểm dữ liệu")
  })
})
