import { describe, expect, it } from "vitest"
import { formatVietnamDate } from "./market-session"

describe("formatVietnamDate", () => {
  it("names the session by its own day, not the viewer's", () => {
    // Midnight in Vietnam is still the previous afternoon in UTC. Read in any
    // zone west of UTC+7, a viewer must still see the session that traded.
    expect(formatVietnamDate("2026-08-10T00:00:00+07:00")).toBe("10/08/2026")
    expect(formatVietnamDate("2026-08-09T17:00:00Z")).toBe("10/08/2026")
  })

  it("reads a plain calendar date as that date", () => {
    expect(formatVietnamDate("2026-06-30")).toBe("30/06/2026")
  })

  it("renders nothing for a value that is not a date", () => {
    expect(formatVietnamDate("")).toBe("")
    expect(formatVietnamDate("not-a-date")).toBe("")
  })
})
