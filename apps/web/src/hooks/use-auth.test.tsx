/** @vitest-environment jsdom */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { QUERY_DEFAULTS } from "@/components/providers/query-provider"
import { ApiUnavailableError, connectionStatus } from "@/lib/connection-status"

import { useAuth } from "./use-auth"

vi.mock("@/app/(auth)/actions", () => ({ logoutAction: vi.fn() }))

/**
 * Retries are switched off here so the assertions land in milliseconds; the
 * policy they would run under is asserted separately against QUERY_DEFAULTS.
 */
function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { ...QUERY_DEFAULTS.queries, retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe("useAuth session read", () => {
  beforeEach(() => {
    connectionStatus.reset()
  })

  afterEach(() => {
    cleanup()
    connectionStatus.reset()
    vi.unstubAllGlobals()
  })

  it("treats an unreachable API as waiting, not as a signed-out session", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: "Unable to resolve session" }), { status: 503 }),
      ),
    )

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isPending).toBe(false))
    expect(connectionStatus.get()).toBe("waiting")
    expect(result.current.user).toBeNull()
  })

  it("clears the wait once the handler answers", async () => {
    connectionStatus.reportWaiting("/api/auth/me")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ user: { id: 1, email: "a@b.c" } }), { status: 200 }),
      ),
    )

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true))
    expect(connectionStatus.get()).toBe("ready")
  })

  it("keeps the outage off the route error boundary and worth retrying", () => {
    const outage = new ApiUnavailableError(undefined, 503)

    expect(QUERY_DEFAULTS.queries.throwOnError(outage)).toBe(false)
    expect(QUERY_DEFAULTS.queries.retry(0, outage)).toBe(true)
  })
})
