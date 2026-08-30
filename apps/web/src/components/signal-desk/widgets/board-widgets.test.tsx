// @vitest-environment jsdom
/**
 * The seven drawings a board added, each on the frame shape it is chosen for.
 *
 * Charts are asserted on their arithmetic and their chrome rather than on their
 * pixels: recharts renders into a zero-sized container under jsdom, so a test
 * that checked bars would be checking nothing. What *is* worth holding is what
 * each widget does before it hands anything to a renderer — the running balance
 * of a waterfall, the cell a comparison colours, the slice a donut refuses.
 */

import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { Frame, Provenance } from "@/lib/alpha-desk/types"

import { BulletWidget } from "./bullet"
import { CaptionWidget } from "./caption"
import { ComparisonTableWidget } from "./comparison-table"
import { DonutWidget } from "./donut"
import { GroupedBarWidget } from "./grouped-bar"
import { TextCardWidget } from "./text-card"
import { steps, WaterfallWidget } from "./waterfall"

afterEach(cleanup)

const PROVENANCE: Provenance = {
  source: "store",
  asOf: "2026-08-20T00:00:00+00:00",
  sessionsUsed: 2,
  health: "normal",
  reason: null,
}

function frame(partial: Partial<Frame> & Pick<Frame, "columns" | "rows">): Frame {
  return {
    kind: "table",
    unit: null,
    labels: Object.fromEntries(partial.columns.map((name) => [name, name])),
    ...partial,
  }
}

const COMPARISON = frame({
  kind: "table",
  columns: ["symbol", "roe", "roa"],
  rows: [
    ["VIC", 4.2, 0.6],
    ["VCB", 18.9, 1.8],
  ],
  unit: "%",
  cellRoles: [
    { row: 0, column: "roe", role: "loser" },
    { row: 1, column: "roe", role: "winner" },
  ],
})

describe("comparison_table", () => {
  it("colours the cell that won and leaves the rest alone", () => {
    render(
      <ComparisonTableWidget
        frame={COMPARISON}
        options={{ entity: "symbol", metrics: ["roe", "roa"] }}
        provenance={PROVENANCE}
      />,
    )
    const winner = screen.getByRole("rowheader", { name: "VCB" }).closest("tr")
    const cells = within(winner as HTMLElement).getAllByRole("cell")

    expect(cells[0]).toHaveStyle({ color: "hsl(var(--widget-up))" })
    // ROA was not marked, so it keeps the page's ink. A row colour could not
    // have said that, which is the whole reason the roles are per cell.
    expect(cells[1].getAttribute("style")).toBe(null)
  })

  it("says in words what it says in colour", () => {
    render(
      <ComparisonTableWidget
        frame={COMPARISON}
        options={{ entity: "symbol", metrics: ["roe"] }}
        provenance={PROVENANCE}
      />,
    )
    const winner = screen.getByRole("rowheader", { name: "VCB" }).closest("tr")

    expect(
      within(winner as HTMLElement).getAllByRole("cell")[0].getAttribute("title"),
    ).toBe("winner")
  })

  it("draws a dash for a cell with no number rather than a zero", () => {
    render(
      <ComparisonTableWidget
        frame={frame({
          columns: ["symbol", "roe"],
          rows: [["VIC", null]],
        })}
        options={{ entity: "symbol", metrics: ["roe"] }}
        provenance={PROVENANCE}
      />,
    )

    expect(screen.getByRole("cell", { name: "—" })).toBeInTheDocument()
  })

  it("says so rather than drawing an empty table", () => {
    render(
      <ComparisonTableWidget
        frame={frame({ columns: ["symbol"], rows: [] })}
        options={{}}
        provenance={PROVENANCE}
      />,
    )

    expect(screen.getByText("Không có gì để đối chiếu.")).toBeInTheDocument()
  })
})

describe("grouped_bar", () => {
  it("names the measures it drew, for a reader who cannot see the chart", () => {
    render(
      <GroupedBarWidget
        frame={COMPARISON}
        options={{ category: "symbol", series: ["roe", "roa"] }}
        provenance={PROVENANCE}
      />,
    )

    expect(screen.getByRole("img", { name: "So sánh roe, roa" })).toBeInTheDocument()
  })

  it("says so rather than drawing an empty chart", () => {
    render(
      <GroupedBarWidget
        frame={frame({ columns: ["symbol"], rows: [["VIC"]] })}
        options={{ category: "symbol", series: [] }}
        provenance={PROVENANCE}
      />,
    )

    expect(screen.getByText("Không có nhóm nào để so.")).toBeInTheDocument()
  })
})

describe("donut", () => {
  const PARTS = frame({
    columns: ["bucket", "share"],
    rows: [
      ["A", 40],
      ["B", 30],
      ["C", 20],
      ["D", 10],
    ],
    unit: "%",
  })

  it("labels itself by what it divides", () => {
    render(
      <DonutWidget
        frame={PARTS}
        options={{ label: "bucket", value: "share" }}
        provenance={PROVENANCE}
      />,
    )

    expect(screen.getByRole("img", { name: "Cơ cấu theo share" })).toBeInTheDocument()
  })

  it("says so rather than drawing an empty ring", () => {
    render(
      <DonutWidget
        frame={frame({ columns: ["bucket", "share"], rows: [["A", 0]] })}
        options={{ label: "bucket", value: "share" }}
        provenance={PROVENANCE}
      />,
    )

    expect(screen.getByText("Không có phần nào để chia.")).toBeInTheDocument()
  })
})

describe("waterfall", () => {
  it("stands each bar on the balance the one before it left", () => {
    // The arithmetic, not the rendering: a chart whose numbers are only checked
    // by looking at it is a chart nobody checked.
    expect(steps(["a", "b", "c"], [100, -30, 20])).toEqual([
      { label: "a", base: 0, step: 100, total: 100 },
      { label: "b", base: 100, step: -30, total: 70 },
      { label: "c", base: 70, step: 20, total: 90 },
    ])
  })

  it("skips a step with no number rather than treating it as zero", () => {
    expect(steps(["a", "b", "c"], [100, null, 20])).toEqual([
      { label: "a", base: 0, step: 100, total: 100 },
      { label: "c", base: 100, step: 20, total: 120 },
    ])
  })

  it("says so rather than drawing an empty run", () => {
    render(
      <WaterfallWidget
        frame={frame({ columns: ["label", "value"], rows: [["a", null]] })}
        options={{}}
        provenance={PROVENANCE}
      />,
    )

    expect(screen.getByText("Không có bước nào để cộng dồn.")).toBeInTheDocument()
  })
})

describe("bullet", () => {
  it("draws one row per value and names what the mark is", () => {
    render(
      <BulletWidget
        frame={frame({
          columns: ["label", "value", "benchmark"],
          rows: [
            ["VIC", 12, 20],
            ["VCB", 24, 20],
          ],
        })}
        options={{ label: "label", value: "value", benchmark: "benchmark" }}
        provenance={PROVENANCE}
      />,
    )

    expect(screen.getByText("VIC")).toBeInTheDocument()
    expect(screen.getByText("Vạch dọc là benchmark.")).toBeInTheDocument()
  })

  it("says so rather than drawing an empty track", () => {
    render(
      <BulletWidget
        frame={frame({ columns: ["label", "value"], rows: [] })}
        options={{}}
        provenance={PROVENANCE}
      />,
    )

    expect(screen.getByText("Không có mức nào để so.")).toBeInTheDocument()
  })
})

describe("text_card", () => {
  it("prints what the frame holds and composes nothing of its own", () => {
    render(
      <TextCardWidget
        frame={frame({
          columns: ["label", "note"],
          rows: [["Ghi chú", "Kỳ gần nhất chưa soát xét."]],
        })}
        options={{ label: "label", text: "note" }}
        provenance={PROVENANCE}
      />,
    )

    expect(screen.getByText("Kỳ gần nhất chưa soát xét.")).toBeInTheDocument()
  })
})

describe("caption", () => {
  const value = (text: string, column: string) => ({
    text,
    raw: 1,
    unit: "%",
    frame: "f0",
    row: 1,
    column,
  })

  it("marks each figure and says which cell it came from", () => {
    render(
      <CaptionWidget
        caption={{
          kind: "caption",
          template: "ROE của VCB là {a} so với {b}.",
          text: "ROE của VCB là 18,9% so với 4,2%.",
          refs: { a: value("18,9%", "roe"), b: value("4,2%", "roe") },
          span: 12,
        }}
      />,
    )

    const marks = document.querySelectorAll("mark")
    expect(Array.from(marks).map((mark) => mark.textContent)).toEqual([
      "18,9%",
      "4,2%",
    ])
    expect(marks[0].getAttribute("title")).toBe("roe · dòng 2")
  })

  it("draws a hole as itself rather than as a gap", () => {
    // The server refuses this, so one arriving means the two builds disagree —
    // and a sentence with a visible hole is a hole the reader can see.
    render(
      <CaptionWidget
        caption={{
          kind: "caption",
          template: "ROE là {a}.",
          text: "ROE là {a}.",
          refs: {},
          span: 12,
        }}
      />,
    )

    expect(screen.getByText(/\{a\}/)).toBeInTheDocument()
    expect(document.querySelectorAll("mark")).toHaveLength(0)
  })
})
