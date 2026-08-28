// @vitest-environment jsdom
/**
 * The checklist, and the three claims it must not distort.
 *
 * **`unknown` is not a failure.** An unfiled quarter and a condition that was
 * tested and did not hold are different claims, and a widget that drew them the
 * same would be answering a question the store did not.
 *
 * **The wording arrives.** The labels are the Study's constants; this component
 * renders them and composes nothing, because a rephrased condition is a second
 * author of a claim about a company.
 *
 * **The status is not colour alone.** Colour is a hint; the text a screen reader
 * gets is the answer.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { Frame, Provenance } from "@/lib/alpha-desk/types"

import { ConditionChecklistWidget } from "./condition-checklist"

afterEach(cleanup)

const PROVENANCE: Provenance = {
  source: "vnstock",
  asOf: "2026-08-21T09:00:00+00:00",
  sessionsUsed: 250,
  health: "degraded",
  reason: "fewer than 8 quarters stored",
}

const NOTE =
  "Bảng điều kiện mô tả trạng thái dữ liệu tại phiên đã đóng gần nhất."

const FRAME: Frame = {
  kind: "table",
  columns: ["label", "status", "status_text", "value", "unit", "evidence"],
  rows: [
    [
      "Giá đóng cửa còn cách đỉnh 52 tuần trên 5%",
      "met",
      "Đạt",
      -10.92,
      "%",
      "range_band",
    ],
    ["Lợi nhuận nắm giữ 12 tháng dương", "not_met", "Chưa đạt", -10.81, "%", "price_context"],
    ["Lợi nhuận quý gần nhất dương", "unknown", "Chưa rõ", null, "VND", "earnings_quarters"],
  ],
  unit: null,
  labels: {
    label: "Điều kiện",
    status: "Mã trạng thái",
    status_text: "Trạng thái",
    value: "Mức đo được",
    unit: "Đơn vị",
    evidence: "Khối dữ liệu",
  },
}

const OPTIONS = {
  label: "label",
  status: "status",
  value: "value",
  unit: "unit",
  evidence: "evidence",
  note: NOTE,
}

function draw(frame: Frame = FRAME, options: Record<string, unknown> = OPTIONS) {
  return render(
    <ConditionChecklistWidget
      frame={frame}
      options={options}
      provenance={PROVENANCE}
    />,
  )
}

describe("the rows", () => {
  it("draws one row per condition, with the Study's own wording", () => {
    const { container } = draw()

    expect(container.querySelectorAll("li")).toHaveLength(3)
    expect(
      screen.getByText("Giá đóng cửa còn cách đỉnh 52 tuần trên 5%"),
    ).toBeTruthy()
  })

  it("reads each status out as a word, not only as a colour", () => {
    const { container } = draw()

    const words = [...container.querySelectorAll(".sr-only")].map(
      (node) => node.textContent,
    )
    expect(words).toEqual(["Đạt", "Chưa đạt", "Chưa rõ"])
  })

  it("marks the three statuses differently, and never two of them alike", () => {
    const { container } = draw()

    const marks = [...container.querySelectorAll("li svg")].map(
      (node) => node.getAttribute("class") ?? "",
    )
    expect(marks[0]).toContain("text-positive")
    expect(marks[1]).toContain("text-negative")
    expect(marks[2]).toContain("text-caution")
    expect(new Set(marks).size).toBe(3)
  })

  it("prints a measurement with its unit, and an em dash where nothing was measured", () => {
    const { container } = draw()

    expect(container.textContent).toContain("−10,9%")
    // An absent measurement is absent: `0` would be a reading of a quarter
    // nobody filed.
    expect(container.textContent).toContain("—")
    expect(container.textContent).not.toContain("0 VND")
  })

  it("keeps the frame that holds each number reachable without showing it", () => {
    const { container } = draw()

    const first = container.querySelector("li")
    expect(first?.getAttribute("title")).toBe("Số liệu trong khối range_band")
    expect(container.textContent).not.toContain("range_band")
  })
})

describe("the note", () => {
  it("shows the fixed disclosure the server sent", () => {
    const { container } = draw()

    expect(container.textContent).toContain(NOTE)
  })

  it("shows no note when the server sent none, rather than inventing one", () => {
    const { container } = draw(FRAME, { ...OPTIONS, note: undefined })

    expect(container.querySelector("figcaption")).toBeNull()
  })
})

describe("what arrives from somewhere else", () => {
  it("draws a status it has never met as unknown rather than as a failure", () => {
    const { container } = draw({
      ...FRAME,
      rows: [["Một điều kiện nào đó", "pending", "Đang chờ", null, null, "x"]],
    })

    expect(container.querySelectorAll("li")).toHaveLength(1)
    expect(container.querySelector(".sr-only")?.textContent).toBe("Chưa rõ")
  })

  it("reads the first two columns when the server sent no options", () => {
    const { container } = draw(
      {
        ...FRAME,
        columns: ["a", "b"],
        rows: [["Điều kiện A", "met"]],
        labels: { a: "A", b: "B" },
      },
      {},
    )

    expect(screen.getByText("Điều kiện A")).toBeTruthy()
    expect(container.querySelector(".sr-only")?.textContent).toBe("Đạt")
  })

  it("says there is nothing to show rather than drawing an empty list", () => {
    const { container } = draw({ ...FRAME, rows: [] })

    expect(container.querySelector("ul")).toBeNull()
    expect(container.textContent).toContain("Không có điều kiện nào")
  })
})
