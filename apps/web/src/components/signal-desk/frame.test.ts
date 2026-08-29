/**
 * Reading a frame, and the one rule that keeps a reading in one language.
 *
 * A frame carries a number and its unit in separate cells, so a surface prints
 * two things side by side. The number's own magnitude therefore has to be said
 * once — the board's four-character shorthand reads cleanly alone on an axis
 * tick and reads as a second unit the moment something follows it. The real
 * case that named this: an average of 380.000 with a unit of `shares` rendered
 * as "380,00 ng shares", half an abbreviation and half another language.
 */

import { describe, expect, it } from "vitest"

import type { Frame } from "@/lib/alpha-desk/types"

import {
  axisPresentation,
  columnIndex,
  columnRole,
  formatMeasure,
  formatMeasureParts,
  formatNumber,
  formatPercent,
  formatQuantity,
  formatUnit,
  formatValue,
  labelOf,
  numberAt,
  pointRole,
  textAt,
} from "./frame"

const FRAME: Frame = {
  kind: "table",
  columns: ["label", "value", "unit"],
  rows: [["Khối lượng trung bình", 380_000, "shares"]],
  unit: null,
  labels: { label: "Chỉ số", value: "Giá trị" },
}

describe("finding a column", () => {
  it("answers where it is, and -1 for a name nothing carries", () => {
    expect(columnIndex(FRAME, "value")).toBe(1)
    expect(columnIndex(FRAME, "khong_co")).toBe(-1)
    expect(columnIndex(FRAME, undefined)).toBe(-1)
  })

  it("reads a column's Vietnamese, or its own name when the server sent none", () => {
    expect(labelOf(FRAME, "value")).toBe("Giá trị")
    expect(labelOf(FRAME, "unit")).toBe("unit")
  })
})

describe("reading a cell", () => {
  it("answers null for a cell that is absent, short or the wrong type", () => {
    // Null rather than nought, five times over in this directory: a bucket with
    // no number and a bucket with a number of nought are different claims.
    expect(numberAt([1, 2], 5)).toBeNull()
    expect(numberAt(["a"], 0)).toBeNull()
    expect(numberAt([Number.NaN], 0)).toBeNull()
    expect(numberAt([0], 0)).toBe(0)
  })

  it("prints an em dash for a cell nothing filled", () => {
    expect(textAt([], 0)).toBe("—")
    expect(textAt([null], 0)).toBe("—")
  })
})

describe("a number on its own", () => {
  it("uses readable Vietnamese magnitude words without trailing zeroes", () => {
    expect(formatNumber(380_000)).toBe("380\u00a0nghìn")
    expect(formatNumber(4_242_424)).toBe("4,2\u00a0triệu")
    expect(formatNumber(1_200_000_000)).toBe("1,2\u00a0tỷ")
  })

  it("leaves anything under ten thousand alone, digits and all", () => {
    // Rounding these would hide the difference between 812 and 1.204.
    expect(formatNumber(1_204)).toBe("1.204")
    expect(formatNumber(-10.92)).toBe("−10,9")
  })
})

describe("a number a unit follows", () => {
  it("spells the magnitude out, so the unit is the only unit on the line", () => {
    expect(formatQuantity(380_000)).toBe("380\u00a0nghìn")
    expect(formatQuantity(4_242_424)).toBe("4,2\u00a0triệu")
    expect(formatQuantity(1_204)).toBe("1.204")
  })

  it("says a unit the way a Vietnamese reader reads it", () => {
    expect(formatUnit("shares")).toBe("cp")
    expect(formatUnit("VND")).toBe("đồng")
    expect(formatUnit("đ")).toBe("đồng")
    expect(formatUnit("phiên")).toBe("phiên")
    expect(formatUnit("%")).toBe("%")
  })

  it("reads the case that named the rule as one sentence in one language", () => {
    expect(formatMeasure(380_000, "shares")).toBe("380\u00a0nghìn cp")
  })

  it("closes a percentage against its sign and spaces everything else", () => {
    expect(formatMeasure(-10.92, "%")).toBe("−10,9%")
    expect(formatMeasure(71_350, "VND")).toBe("71,4\u00a0nghìn đồng")
  })

  it("falls back to the shorthand when there is no unit to collide with", () => {
    expect(formatMeasure(380_000, null)).toBe("380\u00a0nghìn")
    expect(formatMeasure(380_000, "  ")).toBe("380\u00a0nghìn")
  })

  it("splits the figure from its non-wrapping financial unit", () => {
    expect(formatMeasureParts(71_350, "VND")).toEqual({
      value: "71,4",
      unit: "nghìn đồng",
    })
    expect(formatMeasureParts(89.3, "%")).toEqual({ value: "89,3", unit: "%" })
  })
})

describe("a share of a whole", () => {
  it("is the percentage a reader expects, at the precision the server chose", () => {
    expect(formatPercent(0.1938)).toBe("19,4%")
    expect(formatValue(0.1938, "percent")).toBe("19,4%")
    // A share already stored as a percentage is not multiplied a second time.
    expect(formatValue(19.38, undefined)).toBe("19,4")
  })
})

describe("one chart scale", () => {
  it("states a VND unit once and leaves ticks as short numbers", () => {
    const axis = axisPresentation([45_950, 73_500, 76_800], "VND")

    expect(axis.unit).toBe("nghìn đồng")
    expect(axis.format(73_500)).toBe("73,5")
    expect(axis.measure(73_500)).toBe("73,5\u00a0nghìn đồng")
  })

  it("uses a true minus and one decimal on a billion-dong earnings axis", () => {
    const axis = axisPresentation([-150_000_000_000, 100_000_000_000], "VND")

    expect(axis.unit).toBe("tỷ đồng")
    expect(axis.format(-150_000_000_000)).toBe("−150")
  })
})

describe("what a frame says about its own numbers", () => {
  it("answers nothing for a frame written before frames could say anything", () => {
    // The default has to be silence rather than a colour: every artifact frozen
    // before this existed is one of these, and each has to draw as it drew.
    expect(columnRole(FRAME, "value")).toBeNull()
    expect(pointRole(FRAME, 0)).toBeNull()
  })

  it("answers what the engine declared, per series and per row", () => {
    const declared: Frame = {
      ...FRAME,
      rows: [["Q1", 1, "%"], ["Q2", -1, "%"]],
      columnRoles: { value: "up" },
      pointRoles: ["up", "down"],
    }

    expect(columnRole(declared, "value")).toBe("up")
    expect(columnRole(declared, "label")).toBeNull()
    expect(pointRole(declared, 1)).toBe("down")
  })

  it("answers nothing for a row or a column that is not there", () => {
    const declared: Frame = { ...FRAME, columnRoles: { value: "up" }, pointRoles: ["focus"] }

    expect(columnRole(declared, undefined)).toBeNull()
    expect(columnRole(declared, "missing")).toBeNull()
    expect(pointRole(declared, 4)).toBeNull()
  })
})
