// @vitest-environment jsdom
/**
 * The first render of Alpha Desk never depends on `sessionStorage`.
 *
 * The page is server-rendered (`force-dynamic`), and the server has no tab: it
 * cannot know which Thread this one was reading or which symbol it had as the
 * lens. Seeding state from `sessionStorage` during render therefore produces a
 * browser tree the server HTML does not match — a remembered lens draws a dock
 * chip that was never in the markup — and React throws the whole subtree away
 * and rebuilds it. What the tab remembered is applied after hydration instead.
 *
 * Checked by rendering the pass that has to agree — markup only, no effects —
 * with an empty store and with a full one, and demanding the same output.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderToString } from "react-dom/server"
import { afterEach, describe, expect, it, vi } from "vitest"

import { AlphaDesk } from "./alpha-desk"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))

const KEY = "alpha-desk.session"

/** The markup React commits before any effect runs — the hydration contract. */
function firstPass(session: Record<string, string | null> | null): string {
  window.sessionStorage.clear()
  if (session !== null) window.sessionStorage.setItem(KEY, JSON.stringify(session))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return renderToString(
    <QueryClientProvider client={client}>
      <AlphaDesk />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  window.sessionStorage.clear()
})

describe("a returning tab", () => {
  it("renders the same first pass as a fresh one", () => {
    const fresh = firstPass(null)
    const returning = firstPass({
      threadId: "thread-1",
      turnId: "turn-1",
      activeSymbol: "STB",
    })

    expect(returning).toBe(fresh)
  })

  it("draws no lens chip for the symbol it remembered", () => {
    const returning = firstPass({
      threadId: null,
      turnId: null,
      activeSymbol: "STB",
    })

    expect(returning).not.toContain("ngoài Watchlist")
  })
})
