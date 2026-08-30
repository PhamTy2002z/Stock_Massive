// @vitest-environment jsdom
/**
 * The board the compiler actually produced, drawn.
 *
 * The fixture is the payload the server stores for the VIC-against-VCB question
 * — dumped from the same code path the end-to-end API test asserts on, not
 * written by hand — so a change to the spec breaks a test here rather than
 * drifting past one.
 */

import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { ArtifactPayload, SignalDeskSpecV2 } from "@/lib/alpha-desk/types"

import fixture from "./__fixtures__/board-v2-compare.json"
import { SignalDeskBoardView } from "./signal-desk-board"

afterEach(cleanup)

const ARTIFACT = fixture as unknown as ArtifactPayload
const SPEC = ARTIFACT.signal_desk_spec as SignalDeskSpecV2

function draw(spec: SignalDeskSpecV2 = SPEC) {
  return render(
    <SignalDeskBoardView
      spec={spec}
      frames={ARTIFACT.frames}
      provenance={ARTIFACT.provenance}
    />,
  )
}

describe("the strip that leads the board", () => {
  it("draws every figure the server resolved, as the string it resolved", () => {
    draw()
    const strip = screen.getByLabelText("Các con số dẫn dắt")

    expect(within(strip).getByText("18,9%")).toBeInTheDocument()
    expect(within(strip).getByText("4,2%")).toBeInTheDocument()
    expect(within(strip).getByText("8,40 nghìn tỷ")).toBeInTheDocument()
  })

  it("colours a figure only where the engine said what it is", () => {
    draw()
    const strip = screen.getByLabelText("Các con số dẫn dắt")

    // The winner and the loser carry the market pair's tokens; the ratio that
    // claimed nothing keeps the page's own ink.
    expect(within(strip).getByText("18,9%")).toHaveStyle({
      color: "hsl(var(--widget-up))",
    })
    expect(within(strip).getByText("4,2%")).toHaveStyle({
      color: "hsl(var(--widget-down))",
    })
    expect(within(strip).getByText("0,4%").getAttribute("style")).toBe(null)
  })

  it("shows a delta as a second cell and never as a subtraction", () => {
    draw()
    const strip = screen.getByLabelText("Các con số dẫn dắt")
    // The previous quarter's own figure, formatted by the server. Nothing here
    // computed a difference from the pair.
    expect(within(strip).getByText("8,30 nghìn tỷ")).toBeInTheDocument()
  })
})

describe("the sections under it", () => {
  it("draws each heading the server wrote", () => {
    draw()

    expect(screen.getByText("Đối chiếu chỉ số")).toBeInTheDocument()
    expect(screen.getByText("Lợi nhuận theo quý")).toBeInTheDocument()
  })

  it("draws the comparison as a table of symbols against metrics", () => {
    draw()
    // The first table on the board. The appendix draws the same frame plainly,
    // so an unscoped query would find both — which is the arrangement working:
    // a reader who cannot read the marks still has every number underneath.
    const comparison = screen.getAllByRole("table")[0]

    expect(
      within(comparison).getByRole("columnheader", { name: "ROE" }),
    ).toBeInTheDocument()
    expect(
      within(comparison).getByRole("rowheader", { name: "VCB" }),
    ).toBeInTheDocument()
    expect(
      within(comparison).getByRole("rowheader", { name: "VIC" }),
    ).toBeInTheDocument()
  })

  it("marks the winning cell rather than the winning row", () => {
    draw()
    const comparison = screen.getAllByRole("table")[0]
    const row = within(comparison)
      .getByRole("rowheader", { name: "VCB" })
      .closest("tr")
    expect(row).not.toBeNull()
    const coloured = within(row as HTMLElement)
      .getAllByRole("cell")
      .filter((cell) => cell.getAttribute("style") !== null)

    // ROE and ROA are marked; the margin and the leverage are not — which is
    // the claim a comparison makes and a row colour could not.
    expect(coloured).toHaveLength(2)
  })

  it("draws the caption with each figure marked and traceable", () => {
    draw()

    const marks = document.querySelectorAll("mark")
    expect(Array.from(marks).map((mark) => mark.textContent)).toEqual([
      "18,9%",
      "4,2%",
    ])
    expect(marks[0].getAttribute("title")).toContain("roe")
  })

  it("puts the plain table in the appendix and nowhere else", () => {
    draw()

    expect(screen.getByText("Số liệu đầy đủ")).toBeInTheDocument()
  })
})

describe("a board the server drew", () => {
  it("says so, in a line the reader can see", () => {
    draw({ ...SPEC, autoComposed: true })

    expect(
      screen.getByText("Bảng được dựng tự động từ dữ liệu đã tính."),
    ).toBeInTheDocument()
  })

  it("says nothing when the model composed it", () => {
    draw()

    expect(
      screen.queryByText("Bảng được dựng tự động từ dữ liệu đã tính."),
    ).not.toBeInTheDocument()
  })
})

describe("a block whose numbers did not come from this store", () => {
  it("carries a badge saying where they did come from", () => {
    const spec: SignalDeskSpecV2 = {
      ...SPEC,
      sections: SPEC.sections.map((section, index) =>
        index !== 0
          ? section
          : {
              ...section,
              blocks: section.blocks.map((block) =>
                block.kind === "visual" ? { ...block, source: "web" as const } : block,
              ),
            },
      ),
    }
    draw(spec)

    expect(screen.getAllByText("Nguồn web").length).toBeGreaterThan(0)
  })

  it("carries none at all for this deployment's own measurement", () => {
    draw()

    expect(screen.queryByText("Nguồn web")).not.toBeInTheDocument()
    expect(screen.queryByText("Số tính ra")).not.toBeInTheDocument()
  })
})
