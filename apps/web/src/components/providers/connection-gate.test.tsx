/** @vitest-environment jsdom */

import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query"
import { act, cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { searchStocks } from "@/lib/api"
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
    connectionStatus.reportWaiting("unavailable-operation")
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

  it("stays waiting while any active request is still unavailable", async () => {
    connectionStatus.reportWaiting(
      "http://localhost:8000/api/v1/stocks/symbols/search?q=UNAVAILABLE&limit=20",
    )
    const transitions: string[] = []
    const unsubscribe = connectionStatus.subscribe(() => {
      transitions.push(connectionStatus.get())
    })
    const unavailable = deferred<Response>()
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input)
        if (url.endsWith("/health")) {
          return Promise.resolve(new Response(null, { status: 200 }))
        }
        if (url.includes("q=AVAILABLE")) {
          return Promise.resolve(jsonResponse(200, []))
        }
        return unavailable.promise
      }),
    )
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <ConnectionGate>
          <ActiveQueries />
        </ConnectionGate>
      </QueryClientProvider>,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })

    await act(async () => {
      unavailable.resolve(jsonResponse(503, { detail: "Still unavailable" }))
    })
    unsubscribe()

    expect(transitions).toEqual([])
    expect(screen.getByRole("status")).toBeInTheDocument()
  })
})

function ActiveQueries() {
  useQuery({
    queryKey: ["available"],
    queryFn: () => searchStocks("AVAILABLE"),
    initialData: [],
    staleTime: Infinity,
  })
  useQuery({
    queryKey: ["unavailable"],
    queryFn: () => searchStocks("UNAVAILABLE"),
    initialData: [],
    staleTime: Infinity,
  })
  return <p>Nội dung</p>
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}
