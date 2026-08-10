import { describe, expect, it } from "vitest"
import {
  formatBillions,
  formatDataAge,
  formatPercent,
  formatSessionDate,
  formatVolume,
} from "./format"

describe("formatVolume", () => {
  it("uses M suffix from 1 million", () => {
    expect(formatVolume(1_000_000)).toBe("1.00M")
    expect(formatVolume(12_345_678)).toBe("12.35M")
  })

  it("uses K suffix from 1 thousand", () => {
    expect(formatVolume(1_000)).toBe("1.0K")
    expect(formatVolume(999_999)).toBe("1000.0K")
  })

  it("falls back to locale digits below 1 thousand", () => {
    expect(formatVolume(999)).toBe("999")
    expect(formatVolume(0)).toBe("0")
  })
})

describe("formatPercent", () => {
  it("prefixes non-negative values with +", () => {
    expect(formatPercent(1.234)).toBe("+1.23%")
    expect(formatPercent(0)).toBe("+0.00%")
  })

  it("keeps the native minus sign for negatives", () => {
    expect(formatPercent(-2.5)).toBe("-2.50%")
  })

  it("renders null as a dash", () => {
    expect(formatPercent(null)).toBe("-")
  })
})

describe("formatBillions", () => {
  it("scales by magnitude", () => {
    expect(formatBillions(2.5e12)).toBe("2.5T")
    expect(formatBillions(3e9)).toBe("3.0B")
    expect(formatBillions(4.56e6)).toBe("4.6M")
  })

  it("scales negatives by absolute magnitude", () => {
    expect(formatBillions(-3e9)).toBe("-3.0B")
  })

  it("falls back to locale digits below 1 million", () => {
    expect(formatBillions(1234)).toBe((1234).toLocaleString())
  })
})

describe("formatDataAge", () => {
  it("names the coarsest unit that still says something", () => {
    expect(formatDataAge(30)).toBe("dưới 1 phút")
    expect(formatDataAge(90)).toBe("1 phút")
    expect(formatDataAge(82_779)).toBe("22 giờ")
    expect(formatDataAge(8 * 86_400)).toBe("8 ngày")
  })

  it("rounds down, so freshly written data is never aged up", () => {
    // A session read the following evening: one session old, not two days.
    expect(formatDataAge(47 * 3600)).toBe("1 ngày")
    expect(formatDataAge(3599)).toBe("59 phút")
  })

  it("reads a clock-skewed negative age as brand new", () => {
    expect(formatDataAge(-5)).toBe("dưới 1 phút")
  })
})

describe("formatSessionDate", () => {
  it("renders dd/mm/yyyy", () => {
    expect(formatSessionDate("2026-08-08")).toBe("08/08/2026")
  })

  it("renders empty string for missing input", () => {
    expect(formatSessionDate(undefined)).toBe("")
    expect(formatSessionDate("")).toBe("")
  })
})
