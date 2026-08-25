// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { DEFAULT_MONITOR_STATE, type MarketMonitorUrlApi } from "@/lib/market-monitor/url-state"

import { MonitorNavigation } from "./monitor-navigation"
import { MonitorStatusProvider } from "./monitor-status"

afterEach(cleanup)

beforeEach(() => {
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    callback(0)
    return 1
  })
})

function urlApi(): MarketMonitorUrlApi {
  return {
    state: DEFAULT_MONITOR_STATE,
    setLens: vi.fn(),
    push: vi.fn(),
    replace: vi.fn(),
  }
}

describe("Market Monitor navigation", () => {
  it("exposes five tabs and moves through them with arrow keys", () => {
    const url = urlApi()
    render(<MonitorStatusProvider><MonitorNavigation url={url} /></MonitorStatusProvider>)

    const overview = screen.getByRole("tab", { name: "Tổng quan" })
    fireEvent.keyDown(overview, { key: "ArrowRight" })
    expect(url.setLens).toHaveBeenCalledWith("breadth")

    fireEvent.keyDown(overview, { key: "End" })
    expect(url.setLens).toHaveBeenCalledWith("stocks")
  })

  it("keeps exchange, horizon and date changes in replace history", () => {
    const url = urlApi()
    render(<MonitorStatusProvider><MonitorNavigation url={url} /></MonitorStatusProvider>)

    fireEvent.click(screen.getByRole("button", { name: "HNX" }))
    fireEvent.click(screen.getByRole("button", { name: "5P" }))
    fireEvent.change(screen.getByLabelText("Ngày dữ liệu"), { target: { value: "2026-08-20" } })

    expect(url.replace).toHaveBeenCalledWith({ exchange: "HNX" })
    expect(url.replace).toHaveBeenCalledWith({ horizon: 5 })
    expect(url.replace).toHaveBeenCalledWith({ asOf: "2026-08-20" })
  })
})
