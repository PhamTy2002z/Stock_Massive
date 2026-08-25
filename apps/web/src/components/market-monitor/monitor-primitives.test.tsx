// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { MonitorMeta, MonitorState } from "@/lib/market-monitor/api"

import { formatMetric, MonitorStateNotice } from "./monitor-primitives"

afterEach(cleanup)

function meta(state: MonitorState): MonitorMeta {
  const evaluated = state === "unavailable" ? 0 : state === "partial" ? 7 : 10
  return {
    exchange: "HOSE",
    as_of: "2026-08-24T00:00:00+07:00",
    generated_at: "2026-08-24T09:00:00Z",
    state,
    coverage: { eligible: 10, evaluated, missing: 10 - evaluated, state: evaluated === 10 ? "complete" : evaluated === 0 ? "unavailable" : "partial" },
    realtime_coverage: null,
    sources: [],
    issues: state === "disconnected" ? ["realtime_projection_unavailable"] : [],
    method_versions: { breadth: "breadth-v1" },
  }
}

describe("Market Monitor evidence states", () => {
  it.each([
    ["partial", "7/10"],
    ["stale", "Dữ liệu cũ"],
    ["disconnected", "DNSE realtime"],
    ["unavailable", "Chưa có mã nào"],
  ] as const)("renders %s without hiding valid context", (state, copy) => {
    render(<MonitorStateNotice meta={meta(state)} />)
    expect(screen.getByText(new RegExp(copy))).toBeInTheDocument()
  })

  it("renders absence as a dash and never as a fabricated zero", () => {
    expect(formatMetric({ value: null, unit: "VND", as_of: "2026-08-24T00:00:00Z", method: "x", issues: ["unavailable"] })).toBe("—")
    expect(formatMetric({ value: 0, unit: "VND", as_of: "2026-08-24T00:00:00Z", method: "x", issues: [] })).toBe("0 đ")
  })
})
