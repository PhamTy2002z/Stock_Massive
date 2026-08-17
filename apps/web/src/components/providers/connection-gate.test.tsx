/** @vitest-environment jsdom */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { connectionStatus } from "@/lib/connection-status"

import { ConnectionGate } from "./connection-gate"

vi.mock("sonner", () => ({
  toast: { dismiss: vi.fn(), loading: vi.fn() },
}))

describe("ConnectionGate recovery", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    connectionStatus.reset()
  })

  afterEach(() => {
    cleanup()
    connectionStatus.reset()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it("does not flash ready merely because the health probe answers", async () => {
    connectionStatus.reportWaiting()
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 200 })))
    const queryClient = new QueryClient()

    render(
      <QueryClientProvider client={queryClient}>
        <ConnectionGate>
          <p>Nội dung</p>
        </ConnectionGate>
      </QueryClientProvider>,
    )

    expect(screen.getByRole("status")).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })

    expect(screen.getByRole("status")).toBeInTheDocument()
    expect(connectionStatus.get()).toBe("waiting")
  })
})
