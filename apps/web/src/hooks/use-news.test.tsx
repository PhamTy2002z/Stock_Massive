// @vitest-environment jsdom
/**
 * That a refused news feed stays inside the news pane.
 *
 * The app's query defaults send every refusal to the ErrorBoundary, which for
 * this query would take the whole shell down over one pane of headlines — it did
 * exactly that the first time the view met an API that had not deployed the
 * route yet. So this renders through a client holding the *real* defaults
 * (imported, not copied) and asserts the hook opts out: a 404 has to come back
 * as `isError`, not as a thrown render.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor } from "@testing-library/react"

import { QUERY_DEFAULTS } from "@/components/providers/query-provider"

import { useNewsFeed } from "./use-news"

afterEach(cleanup)

beforeEach(() => {
  vi.restoreAllMocks()
})

/** A client on the app's own terms, minus the retries a test should not wait for. */
function appClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { ...QUERY_DEFAULTS.queries, retry: false },
    },
  })
}

function Probe() {
  const feed = useNewsFeed()
  return <div>{feed.isError ? "error-in-pane" : "no-error"}</div>
}

describe("useNewsFeed", () => {
  it("surfaces a refused feed as query state instead of throwing to the boundary", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not Found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    )

    render(
      <QueryClientProvider client={appClient()}>
        <Probe />
      </QueryClientProvider>,
    )

    await waitFor(() => expect(screen.getByText("error-in-pane")).toBeInTheDocument())
  })
})
