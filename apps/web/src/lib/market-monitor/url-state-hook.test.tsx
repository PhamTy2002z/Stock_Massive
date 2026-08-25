// @vitest-environment jsdom

import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it } from "vitest"

import { useMarketMonitorUrlState } from "./url-state"

beforeEach(() => {
  window.history.replaceState(null, "", "/?view=board&lens=flow&exchange=HNX&thread=kept")
})

afterEach(cleanup)

describe("Market Monitor browser history adapter", () => {
  it("hydrates a deep link, pushes lens changes and replaces high-frequency filters", async () => {
    const { result } = renderHook(() => useMarketMonitorUrlState())
    await waitFor(() => expect(result.current.state.lens).toBe("flow"))

    act(() => result.current.setLens("sectors"))
    expect(new URLSearchParams(window.location.search).get("lens")).toBe("sectors")

    act(() => result.current.replace({ exchange: "HOSE", horizon: 5 }))
    const query = new URLSearchParams(window.location.search)
    expect(query.get("exchange")).toBe("HOSE")
    expect(query.get("horizon")).toBe("5")
    expect(query.get("thread")).toBe("kept")
  })

  it("restores durable state from a popstate without touching unrelated params", async () => {
    const { result } = renderHook(() => useMarketMonitorUrlState())
    await waitFor(() => expect(result.current.state.exchange).toBe("HNX"))

    act(() => {
      window.history.pushState(null, "", "/?view=board&lens=stocks&exchange=HOSE&preset=valuation&thread=kept")
      window.dispatchEvent(new PopStateEvent("popstate"))
    })

    expect(result.current.state).toMatchObject({ lens: "stocks", exchange: "HOSE", preset: "valuation" })
    expect(new URLSearchParams(window.location.search).get("thread")).toBe("kept")
  })

  it("keeps independent board and inspector hooks on the same scope", async () => {
    const board = renderHook(() => useMarketMonitorUrlState())
    const inspector = renderHook(() => useMarketMonitorUrlState())
    await waitFor(() => expect(inspector.result.current.state.exchange).toBe("HNX"))

    act(() => board.result.current.replace({ exchange: "HOSE", asOf: "2026-08-22" }))

    await waitFor(() => {
      expect(inspector.result.current.state).toMatchObject({
        exchange: "HOSE",
        asOf: "2026-08-22",
      })
    })
  })
})
