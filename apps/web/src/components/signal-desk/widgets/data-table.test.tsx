// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { Frame, Provenance } from "@/lib/alpha-desk/types"

import { DataTableWidget } from "./data-table"

afterEach(cleanup)

const PROVENANCE: Provenance = {
  source: "vnstock",
  asOf: "2026-08-28T09:00:00+00:00",
  sessionsUsed: 250,
  health: "normal",
  reason: null,
}

function draw(frame: Frame) {
  return render(
    <DataTableWidget frame={frame} options={{}} provenance={PROVENANCE} />,
  )
}

describe("financial table typography", () => {
  it("right-aligns numeric columns and states one common currency scale in the header", () => {
    const frame: Frame = {
      kind: "series",
      columns: ["quarter", "net_profit_vnd", "yoy_pct"],
      rows: [
        ["Q1/2026", 80_000_000_000, 12.14],
        ["Q2/2026", -55_000_000_000, -4.25],
      ],
      unit: "VND",
      labels: {
        quarter: "Quý",
        net_profit_vnd: "Lợi nhuận sau thuế",
        yoy_pct: "So cùng kỳ (%)",
      },
    }

    draw(frame)

    const profitHeader = screen.getByRole("columnheader", {
      name: /Lợi nhuận sau thuế.*tỷ đồng/,
    })
    const percentHeader = screen.getByRole("columnheader", {
      name: /So cùng kỳ.*%/,
    })
    expect(profitHeader.className).toContain("text-right")
    expect(percentHeader.className).toContain("text-right")

    const values = screen.getAllByRole("cell")
    expect(values.find((cell) => cell.textContent === "80")?.className).toContain(
      "font-mono",
    )
    expect(values.find((cell) => cell.textContent === "−55")?.className).toContain(
      "text-right",
    )
    expect(values.find((cell) => cell.textContent === "12,1")?.className).toContain(
      "tabular-nums",
    )
  })

  it("moves a row-level magnitude into the unit column", () => {
    const frame: Frame = {
      kind: "table",
      columns: ["label", "value", "unit"],
      rows: [
        ["Giá đóng cửa", 73_500, "đ"],
        ["Vị thế 52 tuần", 89.3, "%"],
      ],
      unit: null,
      labels: { label: "Chỉ số", value: "Giá trị", unit: "Đơn vị" },
    }

    draw(frame)

    expect(screen.getByText("73,5")).toBeInTheDocument()
    expect(screen.getByText("nghìn đồng")).toBeInTheDocument()
    expect(screen.getByText("89,3")).toBeInTheDocument()
    expect(screen.getByText("%")).toBeInTheDocument()
  })
})
