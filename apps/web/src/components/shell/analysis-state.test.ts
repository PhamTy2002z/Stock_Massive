/**
 * What the Watchlist's five sentences promise.
 *
 * The interesting one is `pending`, which covers two different waits: queued
 * behind other symbols, and held because the Collector has not reached this
 * symbol's session yet. They are the same state and the same colour, so the
 * sentence is the only thing that tells them apart.
 */

import { describe, expect, it } from "vitest"

import type { RunFailure } from "@/lib/alpha"

import {
  dayAndMonth,
  sessionLabel,
  stateSentence,
  waitingForSessionData,
  WAITING_FOR_SESSION_DATA,
} from "./analysis-state"

function failure(code: string | null): RunFailure {
  return { code, message: null, attempts: 1, max_attempts: 3, exhausted: false }
}

describe("dayAndMonth", () => {
  it("reads the API's string without going through a Date", () => {
    expect(dayAndMonth("2026-08-12")).toBe("12/08")
  })

  it("hands back anything it does not recognise, rather than inventing a day", () => {
    expect(dayAndMonth("not-a-day")).toBe("not-a-day")
  })
})

describe("sessionLabel", () => {
  it("names the session rather than calling it today", () => {
    expect(sessionLabel("2026-08-12")).toBe("phiên 12/08")
  })

  it("says so when nothing has closed yet", () => {
    expect(sessionLabel(null)).toBe("chưa có phiên nào chốt dữ liệu")
  })
})

describe("waitingForSessionData", () => {
  it("is the deferral, and only in pending", () => {
    expect(waitingForSessionData("pending", failure(WAITING_FOR_SESSION_DATA))).toBe(true)
    expect(waitingForSessionData("failed", failure(WAITING_FOR_SESSION_DATA))).toBe(false)
  })

  it("is not any other pending failure, and not a missing one", () => {
    expect(waitingForSessionData("pending", failure("llm_transport_error"))).toBe(false)
    expect(waitingForSessionData("pending", null)).toBe(false)
  })
})

describe("stateSentence", () => {
  it("tells the two waits apart", () => {
    expect(stateSentence("pending", "2026-08-12", failure(WAITING_FOR_SESSION_DATA))).toBe(
      "Đang chờ dữ liệu phiên 12/08 về cho mã này.",
    )
    expect(stateSentence("pending", "2026-08-12", null)).toBe(
      "Chưa tới lượt dựng Analysis cho phiên 12/08.",
    )
  })

  it("does not name a session when none has closed", () => {
    expect(stateSentence("pending", null, failure(WAITING_FOR_SESSION_DATA))).toBe(
      "Chưa có phiên nào chốt dữ liệu nên chưa dựng Analysis.",
    )
  })

  it("explains the healthy states too, not only the broken ones", () => {
    expect(stateSentence("ready", "2026-08-12")).toBe("Đã có Analysis cho phiên 12/08.")
    expect(stateSentence("producing", "2026-08-12")).toBe(
      "Đang dựng Analysis cho phiên 12/08.",
    )
  })

  it("does not call an unsupported symbol a failure", () => {
    expect(stateSentence("unsupported", "2026-08-12")).toContain("Lịch sử vẫn đọc được")
    expect(stateSentence("failed", "2026-08-12")).toBe("Chưa có Analysis cho phiên 12/08.")
  })
})
