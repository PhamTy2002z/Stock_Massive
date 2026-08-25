import { describe, expect, it } from "vitest"

import {
  DEFAULT_MONITOR_STATE,
  parseMarketMonitorState,
  recalledMonitorScroll,
  rememberMonitorScroll,
  serializeMarketMonitorState,
  shellViewFromSearch,
} from "./url-state"

describe("Market Monitor URL state", () => {
  it("parses a deep link into typed durable state", () => {
    expect(
      parseMarketMonitorState(
        "?view=board&lens=stocks&exchange=HNX&horizon=5&as_of=2026-08-24&sector=10&preset=flow&sort=foreign_net_20d_vnd&direction=desc",
      ),
    ).toEqual({
      lens: "stocks",
      exchange: "HNX",
      horizon: 5,
      asOf: "2026-08-24",
      sector: "10",
      preset: "flow",
      sort: "foreign_net_20d_vnd",
      direction: "desc",
    })
  })

  it("defaults invalid values without dropping unrelated shell query state", () => {
    const parsed = parseMarketMonitorState(
      "?lens=casino&exchange=UPCOM&horizon=7&as_of=not-a-date&direction=sideways",
    )
    const serialized = serializeMarketMonitorState(parsed, "?thread=abc")

    expect(parsed).toEqual(DEFAULT_MONITOR_STATE)
    expect(new URLSearchParams(serialized).get("thread")).toBe("abc")
    expect(new URLSearchParams(serialized).get("view")).toBe("board")
  })

  it("recognizes only an explicit board shell deep link", () => {
    expect(shellViewFromSearch("?view=board&lens=flow")).toBe("board")
    expect(shellViewFromSearch("?view=news")).toBeNull()
  })

  it("retains one scroll position per lens", () => {
    rememberMonitorScroll(DEFAULT_MONITOR_STATE, 140)
    rememberMonitorScroll({ ...DEFAULT_MONITOR_STATE, lens: "flow" }, 880)

    expect(recalledMonitorScroll(DEFAULT_MONITOR_STATE)).toBe(140)
    expect(recalledMonitorScroll({ ...DEFAULT_MONITOR_STATE, lens: "flow" })).toBe(880)
    expect(recalledMonitorScroll({ ...DEFAULT_MONITOR_STATE, lens: "sectors" })).toBe(0)
    expect(recalledMonitorScroll({ ...DEFAULT_MONITOR_STATE, exchange: "HNX" })).toBe(0)
  })
})
