// @vitest-environment jsdom
/**
 * The four Widgets, from fixtures, with no network anywhere (#90).
 *
 * Every test below renders a component with data already in hand. That is not a
 * testing convenience — it is the property ADR-0012 asks for: a Widget that
 * fetched would re-query today's numbers inside an answer dated to last March,
 * which is the staleness bug the whole registry exists to close. A fetch would
 * fail here, and that is the point.
 */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { MetricComparison } from "./metric-comparison"
import { MetricTrend } from "./metric-trend"
import { RankedSymbols } from "./ranked-symbols"
import { RelativePosition } from "./relative-position"
import {
  AS_OF,
  crossSymbol,
  position,
  ranking,
  series,
  signedCrossSymbol,
  spec,
  unavailable,
} from "./fixtures"

// Vitest globals are off in this project, so nothing unmounts on its own and a
// second `render` in the same file would leave two of everything in the DOM.
afterEach(cleanup)

const CASES = [
  {
    name: "metric_comparison",
    render: () => <MetricComparison spec={spec()} data={crossSymbol()} />,
  },
  {
    name: "ranked_symbols",
    render: () => (
      <RankedSymbols spec={spec({ name: "ranked_symbols" })} data={ranking()} />
    ),
  },
  {
    name: "metric_trend",
    render: () => (
      <MetricTrend spec={spec({ name: "metric_trend" })} data={series()} />
    ),
  },
  {
    name: "relative_position",
    render: () => (
      <RelativePosition
        spec={spec({ name: "relative_position" })}
        data={position()}
      />
    ),
  },
]

describe.each(CASES)("$name", ({ render: renderCase }) => {
  it("carries its data date where a reader can see it", () => {
    render(renderCase())

    expect(screen.getByText(/Dữ liệu ngày/)).toBeInTheDocument()
  })

  it("states its reading in words as well as in the picture", () => {
    const { container } = render(renderCase())
    const summary = container.querySelector("figure > p:not(.sr-only)")

    expect(summary).not.toBeNull()
    expect(summary?.textContent?.length ?? 0).toBeGreaterThan(20)
  })

  it("describes the picture for a screen reader without walling it off", () => {
    const { container } = render(renderCase())

    // The description is a sibling, not an `aria-label` on a `role="img"`
    // wrapper — that role makes every descendant presentational, which would
    // hide the very rows a screen-reader user needs.
    const description = container.querySelector("figure > p.sr-only")
    expect(description?.textContent?.length ?? 0).toBeGreaterThan(20)
    expect(container.querySelector('[role="img"]')).toBeNull()
  })

  it("offers a data table equivalent, operated from the keyboard", () => {
    render(renderCase())
    const toggle = screen.getByRole("button", { name: "Xem bảng dữ liệu" })

    // A real button rather than a clickable div: that is what makes it
    // tabbable, Enter- and Space-activated, and announced as a control,
    // without this component reimplementing any of the three.
    expect(toggle.tagName).toBe("BUTTON")
    expect(toggle).toHaveAttribute("aria-expanded", "false")
    toggle.focus()
    expect(toggle).toHaveFocus()

    fireEvent.click(toggle)

    const table = screen.getByRole("table")
    expect(within(table).getAllByRole("row").length).toBeGreaterThan(1)
    expect(screen.getByRole("button", { name: "Ẩn bảng dữ liệu" })).toHaveAttribute(
      "aria-expanded",
      "true"
    )
  })

  it("puts the reading outside the disclosure, and the table inside it", () => {
    const { container } = render(renderCase())

    // A collapsed disclosure is out of the accessibility tree by design, and
    // the button announces it. So what a screen-reader user must not have to
    // open it for — the reading and the data date — sits outside.
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(screen.getByRole("table", { hidden: true })).toBeInTheDocument()
    expect(container.querySelector("figure > p:not(.sr-only)")).not.toBeNull()
    expect(screen.getByText(/Dữ liệu ngày/)).toBeVisible()
  })

  it("removes its transitions when the reader asks for reduced motion", () => {
    const { container } = render(renderCase())
    const figure = container.querySelector("figure")

    expect(figure?.className).toContain("motion-reduce:transition-none")
  })

  it("never forces the page to scroll sideways", () => {
    const { container } = render(renderCase())

    // Every Widget is width-constrained at its root, so a long row shrinks or
    // wraps rather than pushing the transcript out.
    expect(container.querySelector("figure")?.className).toContain("min-w-0")
    expect(container.querySelector("[data-widget-figure]")?.className).toContain(
      "overflow-hidden"
    )
  })
})

describe("metric_comparison", () => {
  it("does not let colour carry the sign on its own", () => {
    render(<MetricComparison spec={spec()} data={signedCrossSymbol()} />)

    // The arrow rides in the visible label, the word rides in the table, and
    // the key that pairs the two is announced rather than shown as swatches.
    expect(screen.getByText("▲ 4,20%")).toBeInTheDocument()
    expect(screen.getByText("▼ -12,50%")).toBeInTheDocument()
    const table = screen.getByRole("table", { hidden: true })
    expect(within(table).getByText("tăng")).toBeInTheDocument()
    expect(within(table).getByText("giảm")).toBeInTheDocument()
    expect(screen.getByText("▲ tăng, ▼ giảm")).toHaveClass("sr-only")
  })

  it("draws an unsigned field in one neutral colour rather than inventing a direction", () => {
    render(<MetricComparison spec={spec()} data={crossSymbol()} />)

    expect(screen.queryByText(/▲/)).not.toBeInTheDocument()
  })

  it("names the leader and the laggard in its summary", () => {
    const { container } = render(<MetricComparison spec={spec()} data={crossSymbol()} />)

    expect(container.querySelector("figure > p:not(.sr-only)")?.textContent).toMatch(/FPT/)
    expect(container.querySelector("figure > p:not(.sr-only)")?.textContent).toMatch(/HPG/)
  })

  it("renders bullets rather than an empty chart when the slice is too thin", () => {
    render(<MetricComparison spec={spec()} data={unavailable()} />)

    expect(document.querySelector("[data-widget-figure]")).toBeNull()
    expect(screen.getAllByRole("listitem").length).toBeGreaterThan(0)
    expect(screen.getByText(/Dữ liệu ngày/)).toBeInTheDocument()
  })

  it("scales a wholly negative field by magnitude rather than by maximum", () => {
    const { container } = render(
      <MetricComparison
        spec={spec()}
        data={crossSymbol({
          unit: "percent",
          points: [
            { symbol: "FPT", value: -4, details: {}, refusal: null },
            { symbol: "VCB", value: -20, details: {}, refusal: null },
          ],
        })}
      />
    )
    const widths = Array.from(
      container.querySelectorAll<HTMLElement>('[data-widget-figure] span[style*="width"]')
    ).map((node) => node.style.width)

    expect(widths).toEqual(["20%", "100%"])
  })
})

describe("ranked_symbols", () => {
  it("is a list first, so a narrow screen stacks rather than scrolls", () => {
    render(<RankedSymbols spec={spec({ name: "ranked_symbols" })} data={ranking()} />)

    expect(screen.getByRole("list")).toBeInTheDocument()
    expect(screen.getAllByRole("listitem")).toHaveLength(3)
  })

  it("draws bars only where their length carries meaning", () => {
    const { container: measurable } = render(
      <RankedSymbols spec={spec({ name: "ranked_symbols" })} data={ranking()} />
    )
    const { container: ratio } = render(
      <RankedSymbols
        spec={spec({ name: "ranked_symbols" })}
        data={ranking({
          sort_by: "provider_pe",
          rows: [
            { symbol: "FPT", provider_pe: 18.2 },
            { symbol: "VCB", provider_pe: 12.7 },
          ],
        })}
      />
    )

    expect(
      measurable.querySelectorAll('[data-widget-figure] span[style*="width"]').length
    ).toBe(3)
    // A ratio has no zero to measure from, so it gets rank numbers and no bars.
    expect(ratio.querySelectorAll('[data-widget-figure] span[style*="width"]').length).toBe(0)
  })

  it("says how much of the matched set is shown", () => {
    const { container } = render(
      <RankedSymbols spec={spec({ name: "ranked_symbols" })} data={ranking()} />
    )

    expect(container.querySelector("figure > p:not(.sr-only)")?.textContent).toContain("3/30")
  })
})

describe("metric_trend", () => {
  it("draws a path whose points come from the fixture", () => {
    const { container } = render(
      <MetricTrend spec={spec({ name: "metric_trend" })} data={series()} />
    )
    const path = container.querySelector("path")

    // Five points, so four line segments after the initial move.
    expect(path?.getAttribute("d")?.match(/L /g)).toHaveLength(4)
  })

  it("falls back to bullets rather than drawing two points as a trend", () => {
    render(
      <MetricTrend
        spec={spec({ name: "metric_trend" })}
        data={series({
          series: [
            { date: "2026-08-13", value: 1 },
            { date: AS_OF, value: 2 },
          ],
        })}
      />
    )

    expect(document.querySelector("[data-widget-figure]")).toBeNull()
    expect(screen.getAllByRole("listitem")).toHaveLength(2)
  })
})

describe("relative_position", () => {
  it("places a percentile against the Universe", () => {
    const { container } = render(
      <RelativePosition spec={spec({ name: "relative_position" })} data={position()} />
    )

    expect(container.querySelector("figure > p:not(.sr-only)")?.textContent).toContain("82%")
  })

  it("states the value as text when there is no sanctioned range to place it in", () => {
    render(
      <RelativePosition
        spec={spec({ name: "relative_position" })}
        data={crossSymbol({
          kind: "position",
          unit: "vnd",
          points: [{ symbol: "FPT", value: 95_400, details: {}, refusal: null }],
        })}
      />
    )

    expect(document.querySelector("[data-widget-figure]")).toBeNull()
    expect(screen.getByText(/Chưa có biên độ tham chiếu/)).toBeInTheDocument()
  })
})
